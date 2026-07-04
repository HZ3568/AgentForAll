from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.run_event import RunEvent
from backend.app.repositories.conversations import ConversationRepository
from backend.app.repositories.users import UserRepository
from backend.app.runtime.session_manager import AgentSessionManager
from backend.app.services.agent_service import AgentService


class NeverCalledAdapter:
    def run_turn(self, **kwargs):
        raise AssertionError("Queued cancellation should not execute adapter.")


def test_cancel_queued_run_marks_cancelled(db_session: Session, tmp_path):
    user = UserRepository(db_session).create_user("alice", "alice@example.com", "hash")
    conversation = ConversationRepository(db_session).create_for_user(user.id, "Cancel")
    manager = AgentSessionManager(adapter=NeverCalledAdapter(), workspace_root=tmp_path)
    service = AgentService(db_session, session_manager=manager)
    created = service.create_run(user_id=user.id, conversation_id=conversation.id, content="cancel me")

    cancelled = service.cancel_run(user_id=user.id, run_id=created.run.id)
    events = list(db_session.scalars(select(RunEvent).where(RunEvent.run_id == created.run.id)))

    assert cancelled.status == "cancelled"
    assert "run_cancel_requested" in {event.event_type for event in events}
    assert "run_cancelled" in {event.event_type for event in events}


def test_cancel_completed_run_keeps_succeeded_status(db_session: Session, tmp_path):
    from backend.tests.test_agent_service import FakeAdapter

    user = UserRepository(db_session).create_user("alice", "alice@example.com", "hash")
    conversation = ConversationRepository(db_session).create_for_user(user.id, "Cancel")
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    service = AgentService(db_session, session_manager=manager)
    result = service.run_turn(user_id=user.id, conversation_id=conversation.id, content="finish")

    cancelled = service.cancel_run(user_id=user.id, run_id=result.run.id)

    assert cancelled.status == "succeeded"

