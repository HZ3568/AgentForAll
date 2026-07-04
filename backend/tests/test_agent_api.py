from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.v1.agent import get_agent_service
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models.agent_run import AgentRun
from backend.app.models.message import Message
from backend.app.models.run_event import RunEvent
from backend.app.models.tool_call import ToolCall
from backend.app.runtime.session_manager import AgentSessionManager
from backend.app.runtime.types import (
    AgentEventRecord,
    AgentToolCallRecord,
    AgentToolResultRecord,
    AgentTurnResult,
)
from backend.app.services.agent_service import AgentService


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
                )
            ],
            final_text="assistant answer",
        )


def auth_headers(client: TestClient, username: str, email: str) -> dict[str, str]:
    password = "password123"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_conversation(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post("/api/v1/conversations", json={"title": "Agent"}, headers=headers)
    assert response.status_code == 201
    return response.json()


def override_agent_service(manager: AgentSessionManager):
    def _override(db: Annotated[Session, Depends(get_db)]) -> AgentService:
        return AgentService(db, session_manager=manager)

    return _override


def test_agent_turn_creates_messages_run_events_and_tools(
    app_client: TestClient,
    db_session: Session,
    tmp_path,
):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    app.dependency_overrides[get_agent_service] = override_agent_service(manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/turn",
        json={"content": "summarize README"},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["user_message"]["role"] == "user"
    assert body["assistant_messages"][0]["content_text"] == "assistant answer"
    assert body["tool_calls"][0]["tool_name"] == "read_file"

    run = db_session.get(AgentRun, body["run_id"])
    messages = list(db_session.scalars(select(Message).order_by(Message.sequence_no.asc())))
    events = list(db_session.scalars(select(RunEvent).where(RunEvent.run_id == body["run_id"])))
    tool_calls = list(db_session.scalars(select(ToolCall).where(ToolCall.run_id == body["run_id"])))

    assert run is not None
    assert run.status == "succeeded"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert {event.event_type for event in events} >= {"run_started", "assistant_delta", "run_finished"}
    assert tool_calls[0].user_id == messages[0].user_id


def test_other_user_cannot_run_agent_turn(app_client: TestClient, tmp_path):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    app.dependency_overrides[get_agent_service] = override_agent_service(manager)
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/turn",
        json={"content": "no access"},
        headers=headers_b,
    )

    assert response.status_code == 404


def test_agent_turn_rejects_empty_content(app_client: TestClient, tmp_path):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    app.dependency_overrides[get_agent_service] = override_agent_service(manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/turn",
        json={"content": "   "},
        headers=headers,
    )

    assert response.status_code == 422


def test_agent_turn_failure_marks_run_failed(
    app_client: TestClient,
    db_session: Session,
    tmp_path,
):
    manager = AgentSessionManager(adapter=FakeAdapter(fail=True), workspace_root=tmp_path)
    app.dependency_overrides[get_agent_service] = override_agent_service(manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/turn",
        json={"content": "fail"},
        headers=headers,
    )

    run = db_session.scalar(select(AgentRun))
    assert response.status_code == 500
    assert run is not None
    assert run.status == "failed"
    assert "adapter failed" in run.error_message


def test_agent_turn_conflict_returns_409(app_client: TestClient, tmp_path):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    app.dependency_overrides[get_agent_service] = override_agent_service(manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]

    with manager.conversation_lock(user_id, conversation["id"]):
        response = app_client.post(
            f"/api/v1/agent/conversations/{conversation['id']}/turn",
            json={"content": "blocked"},
            headers=headers,
        )

    assert response.status_code == 409

