from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.v1.agent import get_agent_service, get_db_session_factory, get_run_worker_service
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models.agent_run import AgentRun
from backend.app.models.message import Message
from backend.app.models.run_event import RunEvent
from backend.app.models.tool_call import ToolCall
from backend.app.repositories.messages import MessageRepository
from backend.app.runtime.session_manager import AgentSessionManager
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
        self.calls = []

    def run_turn(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("adapter failed")
        return AgentTurnResult(
            assistant_messages=[
                {
                    "role": "assistant",
                    "content_json": {"type": "text", "text": "streamed answer"},
                    "content_text": "streamed answer",
                }
            ],
            events=[AgentEventRecord(event_type="assistant_delta", event_json={"delta": "streamed answer"})],
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
            final_text="streamed answer",
        )


class FakeStreamingAdapter:
    def run_turn_streaming(self, **kwargs):
        on_event = kwargs.get("on_event")
        on_tool_call = kwargs.get("on_tool_call")
        on_tool_result = kwargs.get("on_tool_result")

        if on_event:
            on_event(AgentEventRecord(event_type="assistant_delta", event_json={"delta": "first "}))
            on_event(AgentEventRecord(event_type="assistant_delta", event_json={"delta": "second"}))
        if on_tool_call:
            on_tool_call(
                AgentToolCallRecord(
                    external_id="tool-1",
                    tool_name="read_file",
                    tool_input_json={"path": "README.md"},
                    status="running",
                )
            )
            on_tool_call(
                AgentToolCallRecord(
                    external_id="tool-1",
                    tool_name="read_file",
                    tool_input_json={"path": "README.md"},
                    status="succeeded",
                )
            )
        if on_tool_result:
            on_tool_result(
                AgentToolResultRecord(
                    tool_call_external_id="tool-1",
                    output_text="README content",
                )
            )
        return AgentTurnResult(
            assistant_messages=[
                {
                    "role": "assistant",
                    "content_json": {"type": "text", "text": "first second"},
                    "content_text": "first second",
                }
            ],
            final_text="first second",
        )


class CapturingHistoryAdapter:
    def __init__(self) -> None:
        self.histories = []

    def run_turn_streaming(self, **kwargs):
        self.histories.append(kwargs["history"])
        return AgentTurnResult(
            assistant_messages=[
                {
                    "role": "assistant",
                    "content_json": {"type": "text", "text": "captured"},
                    "content_text": "captured",
                }
            ],
            final_text="captured",
        )


class ImmediateWorker:
    def __init__(self, db: Session, manager: AgentSessionManager) -> None:
        self.db = db
        self.manager = manager

    def execute_run(self, user_id: str, run_id: str, web_search_enabled: bool = False) -> None:
        try:
            AgentService(self.db, session_manager=self.manager).execute_run(
                user_id=user_id,
                run_id=run_id,
                web_search_enabled=web_search_enabled,
            )
        except AgentTurnExecutionError:
            return


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
    response = client.post("/api/v1/conversations", json={"title": "Streaming"}, headers=headers)
    assert response.status_code == 201
    return response.json()


def install_fake_agent_overrides(db_session: Session, manager: AgentSessionManager) -> None:
    def override_agent_service(db: Annotated[Session, Depends(get_db)]) -> AgentService:
        return AgentService(db, session_manager=manager)

    app.dependency_overrides[get_agent_service] = override_agent_service
    app.dependency_overrides[get_run_worker_service] = lambda: ImmediateWorker(db_session, manager)
    app.dependency_overrides[get_db_session_factory] = lambda: (lambda: db_session)


def test_create_run_executes_and_persists_events(app_client: TestClient, db_session: Session, tmp_path):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "summarize README"},
        headers=headers,
    )

    assert response.status_code == 202
    body = response.json()
    assert body["run_id"]
    assert body["events_url"] == f"/api/v1/agent/runs/{body['run_id']}/events/stream"

    run = db_session.get(AgentRun, body["run_id"])
    messages = list(db_session.scalars(select(Message).order_by(Message.sequence_no.asc())))
    events = list(db_session.scalars(select(RunEvent).where(RunEvent.run_id == body["run_id"])))

    assert run is not None
    assert run.status == "succeeded"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert {event.event_type for event in events} >= {
        "run_queued",
        "user_message_created",
        "run_started",
        "assistant_delta",
        "assistant_message_created",
        "tool_call_started",
        "tool_call_finished",
        "tool_result_created",
        "run_finished",
    }


def test_create_run_passes_web_search_enabled_to_adapter(app_client: TestClient, db_session: Session, tmp_path):
    adapter = FakeAdapter()
    manager = AgentSessionManager(adapter=adapter, workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "今年高考本科分数线", "web_search_enabled": True},
        headers=headers,
    )

    assert response.status_code == 202
    assert adapter.calls[0]["web_search_enabled"] is True


def test_run_status_and_events_are_user_isolated(app_client: TestClient, db_session: Session, tmp_path):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)
    created = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "private"},
        headers=headers_a,
    ).json()

    own_run = app_client.get(f"/api/v1/agent/runs/{created['run_id']}", headers=headers_a)
    other_run = app_client.get(f"/api/v1/agent/runs/{created['run_id']}", headers=headers_b)
    own_events = app_client.get(f"/api/v1/agent/runs/{created['run_id']}/events", headers=headers_a)
    other_events = app_client.get(f"/api/v1/agent/runs/{created['run_id']}/events", headers=headers_b)

    assert own_run.status_code == 200
    assert own_run.json()["status"] == "succeeded"
    assert other_run.status_code == 404
    assert own_events.status_code == 200
    assert own_events.json()["events"]
    assert other_events.status_code == 404


def test_sse_stream_outputs_existing_events_and_finishes(app_client: TestClient, db_session: Session, tmp_path):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    created = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "stream"},
        headers=headers,
    ).json()

    with app_client.stream(
        "GET",
        f"/api/v1/agent/runs/{created['run_id']}/events/stream",
        headers=headers,
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: run_queued" in body
    assert "event: run_finished" in body
    assert "data:" in body


def test_streaming_run_persists_deltas_and_tools_before_final_message(
    app_client: TestClient,
    db_session: Session,
    tmp_path,
):
    manager = AgentSessionManager(adapter=FakeStreamingAdapter(), workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "stream this"},
        headers=headers,
    )

    assert response.status_code == 202
    run_id = response.json()["run_id"]
    messages = list(db_session.scalars(select(Message).order_by(Message.sequence_no.asc())))
    events = list(
        db_session.scalars(
            select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence_no.asc())
        )
    )
    tool_calls = list(db_session.scalars(select(ToolCall).where(ToolCall.run_id == run_id)))

    event_types = [event.event_type for event in events]
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[1].content_text == "first second"
    assert event_types.count("assistant_delta") == 2
    assert event_types.index("assistant_delta") < event_types.index("assistant_message_created")
    assert event_types.index("tool_call_started") < event_types.index("assistant_message_created")
    assert event_types.index("assistant_message_created") < event_types.index("run_finished")
    assert len(tool_calls) == 1
    assert tool_calls[0].status == "succeeded"


def test_active_run_endpoint_returns_current_conversation_run(
    app_client: TestClient,
    db_session: Session,
    tmp_path,
):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    run = AgentRun(
        user_id=user_id,
        conversation_id=conversation["id"],
        status="running",
    )
    db_session.add(run)
    db_session.commit()

    response = app_client.get(
        f"/api/v1/agent/conversations/{conversation['id']}/runs?status=active&limit=1",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == run.id
    assert body["items"][0]["status"] == "running"


def test_tool_call_detail_endpoint_includes_result_and_is_user_isolated(
    app_client: TestClient,
    db_session: Session,
    tmp_path,
):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)
    created = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "read README"},
        headers=headers_a,
    ).json()

    own_response = app_client.get(
        f"/api/v1/agent/runs/{created['run_id']}/tool-calls",
        headers=headers_a,
    )
    other_response = app_client.get(
        f"/api/v1/agent/runs/{created['run_id']}/tool-calls",
        headers=headers_b,
    )

    assert own_response.status_code == 200
    assert other_response.status_code == 404
    body = own_response.json()
    assert body["run_id"] == created["run_id"]
    assert body["items"][0]["tool_name"] == "read_file"
    assert body["items"][0]["result"]["output_text"] == "README content"


def test_second_run_for_same_conversation_is_rejected_while_active(
    app_client: TestClient,
    db_session: Session,
    tmp_path,
):
    manager = AgentSessionManager(adapter=FakeAdapter(), workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]

    with manager.conversation_lock(user_id, conversation["id"]):
        first = app_client.post(
            f"/api/v1/agent/conversations/{conversation['id']}/runs",
            json={"content": "first"},
            headers=headers,
        )

    assert first.status_code == 409


def test_failed_background_run_marks_failed_and_releases_lock(
    app_client: TestClient,
    db_session: Session,
    tmp_path,
):
    manager = AgentSessionManager(adapter=FakeAdapter(fail=True), workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "fail"},
        headers=headers,
    )
    run = db_session.get(AgentRun, response.json()["run_id"])
    events = list(db_session.scalars(select(RunEvent).where(RunEvent.run_id == run.id)))

    assert response.status_code == 202
    assert run.status == "failed"
    assert "adapter failed" in run.error_message
    assert "run_failed" in {event.event_type for event in events}

    manager.adapter = FakeAdapter()
    second = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "second"},
        headers=headers,
    )

    assert second.status_code == 202


def test_run_uses_recent_history_before_input_message(
    app_client: TestClient,
    db_session: Session,
    tmp_path,
):
    adapter = CapturingHistoryAdapter()
    manager = AgentSessionManager(adapter=adapter, workspace_root=tmp_path)
    install_fake_agent_overrides(db_session, manager)
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    message_repo = MessageRepository(db_session)
    for index in range(505):
        message_repo.create_user_message(
            user_id=user_id,
            conversation_id=conversation["id"],
            content=f"old {index}",
        )
    db_session.commit()

    response = app_client.post(
        f"/api/v1/agent/conversations/{conversation['id']}/runs",
        json={"content": "latest request"},
        headers=headers,
    )

    assert response.status_code == 202
    captured = adapter.histories[0]
    assert len(captured) == 500
    assert captured[0]["content_text"] == "old 5"
    assert captured[-1]["content_text"] == "old 504"
