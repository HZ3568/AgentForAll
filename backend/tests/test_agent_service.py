from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.agent_run import AgentRun
from backend.app.models.message import Message
from backend.app.models.run_event import RunEvent
from backend.app.models.tool_result import ToolResult
from backend.app.repositories.conversations import ConversationRepository
from backend.app.repositories.users import UserRepository
from backend.app.runtime.session_manager import AgentRunConflict, AgentSessionManager
from backend.app.runtime.types import (
    AgentEventRecord,
    AgentToolCallRecord,
    AgentToolResultRecord,
    AgentTurnResult,
)
from backend.app.services.agent_service import AgentService, AgentTurnExecutionError


class FakeAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def run_turn(self, **kwargs):
        if self.fail:
            raise RuntimeError("adapter failed")
        return AgentTurnResult(
            assistant_messages=[
                {
                    "role": "assistant",
                    "content_json": {"type": "text", "text": "assistant answer"},
                    "content_text": "assistant answer",
                }
            ],
            events=[AgentEventRecord(event_type="assistant_delta", event_json={"text": "assistant answer"})],
            tool_calls=[
                AgentToolCallRecord(
                    external_id="tool-1",
                    tool_name="read_file",
                    tool_input_json={"path": "README.md"},
                    status="succeeded",
                )
            ],
            tool_results=[
                AgentToolResultRecord(
                    tool_call_external_id="tool-1",
                    output_text="README content",
                    output_json={"content": "README content"},
                )
            ],
            final_text="assistant answer",
        )


def create_user_and_conversation(db_session: Session):
    user = UserRepository(db_session).create_user(
        username="alice",
        email="alice@example.com",
        password_hash="hash",
    )
    conversation = ConversationRepository(db_session).create_for_user(user.id, "Agent chat")
    db_session.flush()
    return user, conversation


def test_agent_service_persists_successful_turn(db_session: Session, tmp_path):
    user, conversation = create_user_and_conversation(db_session)
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    service = AgentService(db_session, session_manager=manager)

    result = service.run_turn(
        user_id=user.id,
        conversation_id=conversation.id,
        content="summarize README",
    )

    messages = list(
        db_session.scalars(
            select(Message)
            .where(Message.user_id == user.id, Message.conversation_id == conversation.id)
            .order_by(Message.sequence_no.asc())
        )
    )
    run = db_session.get(AgentRun, result.run.id)
    events = list(db_session.scalars(select(RunEvent).where(RunEvent.run_id == result.run.id)))
    tool_result = db_session.scalar(select(ToolResult))

    assert [message.role for message in messages] == ["user", "assistant"]
    assert [message.sequence_no for message in messages] == [1, 2]
    assert messages[1].content_text == "assistant answer"
    assert run is not None
    assert run.status == "succeeded"
    assert "run_started" in {event.event_type for event in events}
    assert "assistant_delta" in {event.event_type for event in events}
    assert "run_finished" in {event.event_type for event in events}
    assert result.tool_calls[0].tool_name == "read_file"
    assert tool_result is not None
    assert tool_result.output_text == "README content"


def test_agent_service_persists_failed_run(db_session: Session, tmp_path):
    user, conversation = create_user_and_conversation(db_session)
    manager = AgentSessionManager(adapter=FakeAdapter(fail=True), workspace_root=tmp_path)
    service = AgentService(db_session, session_manager=manager)

    with pytest.raises(AgentTurnExecutionError):
        service.run_turn(
            user_id=user.id,
            conversation_id=conversation.id,
            content="fail",
        )

    run = db_session.scalar(select(AgentRun).where(AgentRun.user_id == user.id))
    messages = list(db_session.scalars(select(Message).order_by(Message.sequence_no.asc())))
    events = list(db_session.scalars(select(RunEvent).where(RunEvent.run_id == run.id)))

    assert run.status == "failed"
    assert "adapter failed" in run.error_message
    assert [message.role for message in messages] == ["user"]
    assert "run_failed" in {event.event_type for event in events}


def test_agent_service_rejects_concurrent_turn(db_session: Session, tmp_path):
    user, conversation = create_user_and_conversation(db_session)
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    service = AgentService(db_session, session_manager=manager)

    with manager.conversation_lock(user.id, conversation.id):
        with pytest.raises(AgentRunConflict):
            service.run_turn(
                user_id=user.id,
                conversation_id=conversation.id,
                content="blocked",
            )

