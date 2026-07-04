from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.app.repositories.conversations import ConversationRepository
from backend.app.repositories.run_events import RunEventRepository
from backend.app.repositories.users import UserRepository
from backend.app.services.event_stream_service import EventStreamService
from backend.app.repositories.agent_runs import AgentRunRepository


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_event_stream_service_replays_database_events(db_session: Session):
    user = UserRepository(db_session).create_user("alice", "alice@example.com", "hash")
    conversation = ConversationRepository(db_session).create_for_user(user.id, "Stream")
    run = AgentRunRepository(db_session).create_run(user.id, conversation.id, None, status="succeeded")
    events = RunEventRepository(db_session)
    events.create_event(user.id, conversation.id, run.id, "run_started", {}, 1)
    events.create_event(user.id, conversation.id, run.id, "run_finished", {}, 2)
    db_session.commit()

    service = EventStreamService(poll_interval_seconds=0.01, heartbeat_interval_seconds=0.02)
    chunks = [
        chunk
        async for chunk in service.stream_run_events(
            db_session_factory=lambda: db_session,
            user_id=user.id,
            run_id=run.id,
        )
    ]

    body = "".join(chunks)
    assert "event: run_started" in body
    assert "event: run_finished" in body
    assert "id: 1" in body
