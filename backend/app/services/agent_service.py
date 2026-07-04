from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.agent_run import AgentRun
from backend.app.models.message import Message
from backend.app.models.run_event import RunEvent
from backend.app.models.tool_call import ToolCall
from backend.app.repositories.agent_runs import AgentRunRepository
from backend.app.repositories.conversations import ConversationRepository
from backend.app.repositories.messages import MessageRepository
from backend.app.repositories.run_events import RunEventRepository
from backend.app.repositories.tool_calls import ToolCallRepository
from backend.app.repositories.tool_results import ToolResultRepository
from backend.app.runtime.session_manager import (
    AgentRunConflict,
    AgentSessionManager,
    get_default_agent_session_manager,
)
from backend.app.runtime.types import AgentTurnResult


TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled"}


class AgentConversationNotFound(LookupError):
    """Raised when a user cannot access the target conversation."""


class AgentRunNotFound(LookupError):
    """Raised when a user cannot access the target run."""


class AgentTurnExecutionError(RuntimeError):
    """Raised after a failed run has been persisted."""

    def __init__(self, message: str, run_id: str) -> None:
        super().__init__(message)
        self.run_id = run_id


@dataclass(slots=True)
class AgentRunCreateServiceResult:
    run: AgentRun
    user_message: Message
    events_url: str


@dataclass(slots=True)
class AgentTurnServiceResult:
    run: AgentRun
    user_message: Message
    assistant_messages: list[Message]
    events: list[RunEvent]
    tool_calls: list[ToolCall]


class AgentService:
    def __init__(
        self,
        db: Session,
        session_manager: AgentSessionManager | None = None,
    ) -> None:
        self.db = db
        self.session_manager = session_manager or get_default_agent_session_manager()

    def create_run(
        self,
        *,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> AgentRunCreateServiceResult:
        conversation = ConversationRepository(self.db).get_active_for_user(conversation_id, user_id)
        if conversation is None:
            raise AgentConversationNotFound("Conversation not found.")

        with self.session_manager.conversation_lock(user_id, conversation_id):
            active_runs = AgentRunRepository(self.db).list_active_for_conversation(user_id, conversation_id)
            if active_runs:
                raise AgentRunConflict("Conversation already has a running agent turn.")

            message_repo = MessageRepository(self.db)
            run_repo = AgentRunRepository(self.db)
            event_repo = RunEventRepository(self.db)
            user_message = message_repo.create_user_message(
                user_id=user_id,
                conversation_id=conversation_id,
                content=content,
            )
            run = run_repo.create_run(
                user_id=user_id,
                conversation_id=conversation_id,
                input_message_id=user_message.id,
                status="queued",
            )
            event_repo.create_event(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run.id,
                event_type="run_queued",
                event_json={},
                sequence_no=1,
            )
            event_repo.create_event(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run.id,
                event_type="user_message_created",
                event_json={
                    "message_id": user_message.id,
                    "role": user_message.role,
                    "content_text": user_message.content_text,
                },
                sequence_no=2,
            )
            self.db.commit()
            self.db.refresh(run)
            self.db.refresh(user_message)
            return AgentRunCreateServiceResult(
                run=run,
                user_message=user_message,
                events_url=f"/api/v1/agent/runs/{run.id}/events/stream",
            )

    def execute_run(self, *, user_id: str, run_id: str) -> AgentTurnServiceResult:
        run = AgentRunRepository(self.db).get_for_user(run_id, user_id)
        if run is None:
            raise AgentRunNotFound("Run not found.")

        with self.session_manager.conversation_lock(user_id, run.conversation_id):
            return self._execute_run_locked(user_id=user_id, run_id=run_id)

    def run_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> AgentTurnServiceResult:
        created = self.create_run(user_id=user_id, conversation_id=conversation_id, content=content)
        try:
            return self.execute_run(user_id=user_id, run_id=created.run.id)
        except AgentTurnExecutionError:
            raise
        except Exception as exc:
            raise AgentTurnExecutionError(self._public_error(str(exc)), created.run.id) from exc

    def cancel_run(self, *, user_id: str, run_id: str) -> AgentRun:
        run_repo = AgentRunRepository(self.db)
        run = run_repo.get_for_user(run_id, user_id)
        if run is None:
            raise AgentRunNotFound("Run not found.")

        if run.status in TERMINAL_RUN_STATUSES:
            return run

        original_status = run.status
        run_repo.mark_cancelling(run_id, user_id)
        self._append_event(
            user_id=user_id,
            conversation_id=run.conversation_id,
            run_id=run.id,
            event_type="run_cancel_requested",
            event_json={},
        )
        if original_status == "queued":
            run_repo.mark_cancelled(run_id, user_id)
            self._append_event(
                user_id=user_id,
                conversation_id=run.conversation_id,
                run_id=run.id,
                event_type="run_cancelled",
                event_json={"reason": "cancelled_before_start"},
            )
        self.db.commit()
        self.db.refresh(run)
        return run

    def _execute_run_locked(self, *, user_id: str, run_id: str) -> AgentTurnServiceResult:
        run_repo = AgentRunRepository(self.db)
        message_repo = MessageRepository(self.db)
        run = run_repo.get_for_user(run_id, user_id)
        if run is None:
            raise AgentRunNotFound("Run not found.")
        if run.status in TERMINAL_RUN_STATUSES:
            return self._existing_result(run, user_id)
        if run.status == "cancelling":
            return self._cancel_locked(run, user_id, reason="cancelled_before_start")

        input_message = (
            message_repo.get_for_user(run.input_message_id, user_id)
            if run.input_message_id
            else None
        )
        if input_message is None:
            return self._fail_locked(run, user_id, "Input message not found.")

        run_repo.mark_running(run.id, user_id)
        self._append_event(
            user_id=user_id,
            conversation_id=run.conversation_id,
            run_id=run.id,
            event_type="run_started",
            event_json={},
        )
        self.db.commit()
        self.db.refresh(run)

        history = [
            self._message_to_adapter_dict(message)
            for message in message_repo.list_for_conversation(user_id, run.conversation_id, limit=500)
            if message.sequence_no < input_message.sequence_no
        ]

        try:
            result = self.session_manager.run_turn_unlocked(
                user_id=user_id,
                conversation_id=run.conversation_id,
                history=history,
                user_message=self._message_to_adapter_dict(input_message),
            )
        except Exception as exc:
            result = AgentTurnResult(error=f"{type(exc).__name__}: {exc}")

        self.db.refresh(run)
        if run.status == "cancelling":
            return self._cancel_locked(run, user_id, reason="cancelled_after_execution")
        if result.error:
            return self._fail_locked(run, user_id, result.error)
        return self._persist_success_result(user_id=user_id, run=run, user_message=input_message, result=result)

    def _existing_result(self, run: AgentRun, user_id: str) -> AgentTurnServiceResult:
        messages = MessageRepository(self.db).list_for_conversation(user_id, run.conversation_id, limit=500)
        user_message = next((message for message in messages if message.id == run.input_message_id), None)
        assistant_messages = [
            message for message in messages if message.role == "assistant" and message.sequence_no > (user_message.sequence_no if user_message else 0)
        ]
        return AgentTurnServiceResult(
            run=run,
            user_message=user_message or messages[-1],
            assistant_messages=assistant_messages,
            events=RunEventRepository(self.db).list_for_run(user_id, run.id),
            tool_calls=ToolCallRepository(self.db).list_for_run(user_id, run.id),
        )

    def _persist_success_result(
        self,
        *,
        user_id: str,
        run: AgentRun,
        user_message: Message,
        result: AgentTurnResult,
    ) -> AgentTurnServiceResult:
        if not result.assistant_messages:
            return self._fail_locked(run, user_id, "Agent produced no assistant message.")

        conversation_id = run.conversation_id
        self._persist_adapter_events(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run.id,
            result=result,
        )
        tool_calls = self._persist_tool_records(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run.id,
            result=result,
        )

        message_repo = MessageRepository(self.db)
        assistant_messages: list[Message] = []
        for assistant in result.assistant_messages:
            message = message_repo.create_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content_json=assistant.get("content_json") or {
                    "type": "text",
                    "text": assistant.get("content_text", ""),
                },
                content_text=str(assistant.get("content_text") or ""),
            )
            assistant_messages.append(message)
            self._append_event(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run.id,
                event_type="assistant_message_created",
                event_json={
                    "message_id": message.id,
                    "role": message.role,
                    "content_text": message.content_text,
                },
            )

        self._append_event(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run.id,
            event_type="run_finished",
            event_json={"assistant_message_count": len(assistant_messages)},
        )
        AgentRunRepository(self.db).mark_succeeded(run.id, user_id)
        ConversationRepository(self.db).touch_conversation_for_user(conversation_id, user_id)
        persisted = AgentTurnServiceResult(
            run=run,
            user_message=user_message,
            assistant_messages=assistant_messages,
            events=RunEventRepository(self.db).list_for_run(user_id, run.id),
            tool_calls=tool_calls,
        )
        self.db.commit()
        self._refresh_result(persisted)
        return persisted

    def _fail_locked(self, run: AgentRun, user_id: str, error_message: str) -> AgentTurnServiceResult:
        public_error = self._public_error(error_message)
        self._append_event(
            user_id=user_id,
            conversation_id=run.conversation_id,
            run_id=run.id,
            event_type="run_failed",
            event_json={"message": public_error},
        )
        AgentRunRepository(self.db).mark_failed(run.id, user_id, public_error)
        ConversationRepository(self.db).touch_conversation_for_user(run.conversation_id, user_id)
        self.db.commit()
        self.db.refresh(run)
        raise AgentTurnExecutionError(public_error, run.id)

    def _cancel_locked(self, run: AgentRun, user_id: str, reason: str) -> AgentTurnServiceResult:
        AgentRunRepository(self.db).mark_cancelled(run.id, user_id)
        self._append_event(
            user_id=user_id,
            conversation_id=run.conversation_id,
            run_id=run.id,
            event_type="run_cancelled",
            event_json={"reason": reason},
        )
        ConversationRepository(self.db).touch_conversation_for_user(run.conversation_id, user_id)
        self.db.commit()
        self.db.refresh(run)
        return self._existing_result(run, user_id)

    def _persist_adapter_events(
        self,
        *,
        user_id: str,
        conversation_id: str,
        run_id: str,
        result: AgentTurnResult,
    ) -> list[RunEvent]:
        persisted: list[RunEvent] = []
        for event in result.events:
            event_type = "assistant_delta" if event.event_type == "message_created" else event.event_type
            if event_type in {"run_started", "run_finished"}:
                continue
            persisted.append(
                self._append_event(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    run_id=run_id,
                    event_type=event_type,
                    event_json=event.event_json,
                )
            )
        return persisted

    def _persist_tool_records(
        self,
        *,
        user_id: str,
        conversation_id: str,
        run_id: str,
        result: AgentTurnResult,
    ) -> list[ToolCall]:
        call_repo = ToolCallRepository(self.db)
        result_repo = ToolResultRepository(self.db)
        calls: list[ToolCall] = []
        external_id_map: dict[str, ToolCall] = {}

        for record in result.tool_calls:
            call = call_repo.create_tool_call(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run_id,
                tool_name=record.tool_name,
                tool_input_json=record.tool_input_json,
                status=record.status,
                started_at=record.started_at,
                finished_at=record.finished_at,
            )
            calls.append(call)
            if record.external_id:
                external_id_map[record.external_id] = call
            self._append_event(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run_id,
                event_type="tool_call_started",
                event_json={
                    "tool_call_id": call.id,
                    "tool_name": call.tool_name,
                    "status": "running",
                },
            )

        for record in result.tool_results:
            tool_call = (
                external_id_map.get(record.tool_call_external_id or "")
                if record.tool_call_external_id
                else calls[0]
                if len(calls) == 1
                else None
            )
            if tool_call is None:
                continue
            result_repo.create_tool_result(
                user_id=user_id,
                tool_call_id=tool_call.id,
                output_text=record.output_text,
                output_json=record.output_json,
                evidence_json=record.evidence_json,
                error_type=record.error_type,
            )
            final_status = "failed" if record.error_type else "succeeded"
            call_repo.mark_finished(tool_call.id, user_id, final_status)
            self._append_event(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run_id,
                event_type="tool_call_failed" if record.error_type else "tool_call_finished",
                event_json={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.tool_name,
                    "status": final_status,
                },
            )
            self._append_event(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run_id,
                event_type="tool_result_created",
                event_json={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.tool_name,
                    "status": final_status,
                    "output_text": (record.output_text or "")[:1000],
                },
            )
        return calls

    def _append_event(
        self,
        *,
        user_id: str,
        conversation_id: str,
        run_id: str,
        event_type: str,
        event_json: dict[str, Any] | list[Any] | None,
    ) -> RunEvent:
        repo = RunEventRepository(self.db)
        return repo.create_event(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run_id,
            event_type=event_type,
            event_json=event_json,
            sequence_no=repo.get_next_sequence_no(run_id, user_id),
        )

    def _message_to_adapter_dict(self, message: Message) -> dict[str, Any]:
        return {
            "id": message.id,
            "role": message.role,
            "content_json": message.content_json,
            "content_text": message.content_text,
            "sequence_no": message.sequence_no,
        }

    def _refresh_result(self, result: AgentTurnServiceResult) -> None:
        for item in [result.run, result.user_message, *result.assistant_messages, *result.events, *result.tool_calls]:
            self.db.refresh(item)

    def _public_error(self, message: str) -> str:
        return message[:1000] if message else "Agent run failed."
