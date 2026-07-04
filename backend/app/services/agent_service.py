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


class AgentConversationNotFound(LookupError):
    """Raised when a user cannot access the target conversation."""


class AgentTurnExecutionError(RuntimeError):
    """Raised after a failed run has been persisted."""

    def __init__(self, message: str, run_id: str) -> None:
        super().__init__(message)
        self.run_id = run_id


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

    def run_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> AgentTurnServiceResult:
        conversation = ConversationRepository(self.db).get_active_for_user(conversation_id, user_id)
        if conversation is None:
            raise AgentConversationNotFound("Conversation not found.")

        with self.session_manager.conversation_lock(user_id, conversation_id):
            return self._run_turn_locked(
                user_id=user_id,
                conversation_id=conversation_id,
                content=content,
            )

    def _run_turn_locked(
        self,
        *,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> AgentTurnServiceResult:
        message_repo = MessageRepository(self.db)
        run_repo = AgentRunRepository(self.db)
        event_repo = RunEventRepository(self.db)

        history = [
            self._message_to_adapter_dict(message)
            for message in message_repo.list_for_conversation(user_id, conversation_id, limit=500)
        ]
        user_message = message_repo.create_user_message(
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,
        )
        run = run_repo.create_run(
            user_id=user_id,
            conversation_id=conversation_id,
            input_message_id=user_message.id,
        )
        run_repo.mark_running(run.id, user_id)
        events: list[RunEvent] = [
            event_repo.create_event(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run.id,
                event_type="run_started",
                event_json={},
                sequence_no=1,
            )
        ]

        try:
            result = self.session_manager.run_turn_unlocked(
                user_id=user_id,
                conversation_id=conversation_id,
                history=history,
                user_message=self._message_to_adapter_dict(user_message),
            )
            if result.error:
                return self._persist_failed_result(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    run=run,
                    user_message=user_message,
                    result=result,
                    events=events,
                    error_message=result.error,
                )
            persisted = self._persist_success_result(
                user_id=user_id,
                conversation_id=conversation_id,
                run=run,
                user_message=user_message,
                result=result,
                events=events,
            )
            self.db.commit()
            self._refresh_result(persisted)
            return persisted
        except AgentTurnExecutionError:
            raise
        except Exception as exc:
            result = AgentTurnResult(error=f"{type(exc).__name__}: {exc}")
            self._persist_failed_result(
                user_id=user_id,
                conversation_id=conversation_id,
                run=run,
                user_message=user_message,
                result=result,
                events=events,
                error_message=str(exc),
            )
            raise

    def _persist_success_result(
        self,
        *,
        user_id: str,
        conversation_id: str,
        run: AgentRun,
        user_message: Message,
        result: AgentTurnResult,
        events: list[RunEvent],
    ) -> AgentTurnServiceResult:
        if not result.assistant_messages:
            failed = AgentTurnResult(error="Agent produced no assistant message.")
            return self._persist_failed_result(
                user_id=user_id,
                conversation_id=conversation_id,
                run=run,
                user_message=user_message,
                result=failed,
                events=events,
                error_message=failed.error or "Agent failed.",
            )

        message_repo = MessageRepository(self.db)
        assistant_messages: list[Message] = []
        for assistant in result.assistant_messages:
            assistant_messages.append(
                message_repo.create_message(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content_json=assistant.get("content_json") or {
                        "type": "text",
                        "text": assistant.get("content_text", ""),
                    },
                    content_text=str(assistant.get("content_text") or ""),
                )
            )

        events.extend(
            self._persist_adapter_events(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run.id,
                result=result,
                start_sequence_no=len(events) + 1,
            )
        )
        tool_calls = self._persist_tool_records(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run.id,
            result=result,
        )
        events.append(
            RunEventRepository(self.db).create_event(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run.id,
                event_type="run_finished",
                event_json={"assistant_message_count": len(assistant_messages)},
                sequence_no=len(events) + 1,
            )
        )
        AgentRunRepository(self.db).mark_succeeded(run.id, user_id)
        ConversationRepository(self.db).touch_conversation_for_user(conversation_id, user_id)
        return AgentTurnServiceResult(
            run=run,
            user_message=user_message,
            assistant_messages=assistant_messages,
            events=events,
            tool_calls=tool_calls,
        )

    def _persist_failed_result(
        self,
        *,
        user_id: str,
        conversation_id: str,
        run: AgentRun,
        user_message: Message,
        result: AgentTurnResult,
        events: list[RunEvent],
        error_message: str,
    ) -> AgentTurnServiceResult:
        events.extend(
            self._persist_adapter_events(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=run.id,
                result=result,
                start_sequence_no=len(events) + 1,
            )
        )
        if not any(event.event_type == "run_failed" for event in events):
            events.append(
                RunEventRepository(self.db).create_event(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    run_id=run.id,
                    event_type="run_failed",
                    event_json={"message": self._public_error(error_message)},
                    sequence_no=len(events) + 1,
                )
            )
        AgentRunRepository(self.db).mark_failed(run.id, user_id, self._public_error(error_message))
        ConversationRepository(self.db).touch_conversation_for_user(conversation_id, user_id)
        failed = AgentTurnServiceResult(
            run=run,
            user_message=user_message,
            assistant_messages=[],
            events=events,
            tool_calls=[],
        )
        self.db.commit()
        self._refresh_result(failed)
        raise AgentTurnExecutionError(self._public_error(error_message), run.id)

    def _persist_adapter_events(
        self,
        *,
        user_id: str,
        conversation_id: str,
        run_id: str,
        result: AgentTurnResult,
        start_sequence_no: int,
    ) -> list[RunEvent]:
        persisted: list[RunEvent] = []
        repo = RunEventRepository(self.db)
        sequence_no = start_sequence_no
        for event in result.events:
            persisted.append(
                repo.create_event(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    run_id=run_id,
                    event_type=event.event_type,
                    event_json=event.event_json,
                    sequence_no=event.sequence_no or sequence_no,
                )
            )
            sequence_no += 1
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
            if record.error_type:
                call_repo.mark_finished(tool_call.id, user_id, "failed")
            else:
                call_repo.mark_finished(tool_call.id, user_id, "succeeded")
        return calls

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

