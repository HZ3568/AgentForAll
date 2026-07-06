from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.agent_run import AgentRun


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


def create_conversation(client: TestClient, headers: dict[str, str], title: str = "New Chat") -> dict:
    response = client.post("/api/v1/conversations", json={"title": title}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_user_can_create_and_list_own_conversation(app_client: TestClient):
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers, "Alice chat")

    response = app_client.get("/api/v1/conversations", headers=headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == conversation["id"]


def test_other_user_cannot_read_conversation(app_client: TestClient):
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)

    response = app_client.get(f"/api/v1/conversations/{conversation['id']}", headers=headers_b)

    assert response.status_code == 404


def test_user_can_update_own_conversation_title(app_client: TestClient):
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"title": "Updated title"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"


def test_other_user_cannot_update_conversation(app_client: TestClient):
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)

    response = app_client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"title": "No access"},
        headers=headers_b,
    )

    assert response.status_code == 404


def test_user_can_soft_delete_own_conversation(app_client: TestClient):
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    delete_response = app_client.delete(f"/api/v1/conversations/{conversation['id']}", headers=headers)
    list_response = app_client.get("/api/v1/conversations", headers=headers)

    assert delete_response.status_code == 204
    assert list_response.json()["items"] == []


def test_other_user_cannot_delete_conversation(app_client: TestClient):
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)

    delete_response = app_client.delete(f"/api/v1/conversations/{conversation['id']}", headers=headers_b)
    owner_list_response = app_client.get("/api/v1/conversations", headers=headers_a)

    assert delete_response.status_code == 404
    assert owner_list_response.json()["items"][0]["id"] == conversation["id"]


def test_user_cannot_delete_conversation_with_active_run(
    app_client: TestClient,
    db_session: Session,
):
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    db_session.add(
        AgentRun(
            user_id=user_id,
            conversation_id=conversation["id"],
            status="running",
        )
    )
    db_session.commit()

    delete_response = app_client.delete(f"/api/v1/conversations/{conversation['id']}", headers=headers)
    list_response = app_client.get("/api/v1/conversations", headers=headers)

    assert delete_response.status_code == 409
    assert delete_response.json()["detail"] == "Conversation has an active run."
    assert list_response.json()["items"][0]["id"] == conversation["id"]


def test_user_can_list_workspace_files_for_own_conversation(
    app_client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
):
    del db_session
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    workspace = tmp_path / f"user_{user_id}" / f"conv_{conversation['id']}"
    artifact = workspace / "artifacts" / "answer.md"
    scratch = workspace / "scratch" / "notes.txt"
    escaped = tmp_path / f"user_{user_id}" / "outside.txt"
    artifact.parent.mkdir(parents=True)
    scratch.parent.mkdir(parents=True)
    artifact.write_text("artifact", encoding="utf-8")
    scratch.write_text("scratch", encoding="utf-8")
    escaped.write_text("outside", encoding="utf-8")

    class FakeSettings:
        WORKSPACE_ROOT = str(tmp_path)

    monkeypatch.setattr("backend.app.api.v1.conversations.get_settings", lambda: FakeSettings(), raising=False)

    response = app_client.get(
        f"/api/v1/conversations/{conversation['id']}/workspace-files",
        headers=headers,
    )

    assert response.status_code == 200
    paths = {item["relative_path"] for item in response.json()["items"]}
    assert paths == {"artifacts/answer.md"}


def test_user_can_read_runtime_memory_index_for_own_conversation(
    app_client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
):
    del db_session
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    memory_index = tmp_path / f"user_{user_id}" / ".memory" / "MEMORY.md"
    memory_index.parent.mkdir(parents=True)
    memory_index.write_text("# Memory\n\n- Project preference: UTF-8", encoding="utf-8")

    class FakeSettings:
        WORKSPACE_ROOT = str(tmp_path)

    monkeypatch.setattr("backend.app.api.v1.conversations.get_settings", lambda: FakeSettings(), raising=False)

    response = app_client.get(
        f"/api/v1/conversations/{conversation['id']}/memory-index",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["content"] == "# Memory\n\n- Project preference: UTF-8"


def test_user_can_preview_text_workspace_file(
    app_client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
):
    del db_session
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    artifact = tmp_path / f"user_{user_id}" / f"conv_{conversation['id']}" / "artifacts" / "notes.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# Notes\n\nhello", encoding="utf-8")

    class FakeSettings:
        WORKSPACE_ROOT = str(tmp_path)

    monkeypatch.setattr("backend.app.api.v1.conversations.get_settings", lambda: FakeSettings(), raising=False)

    response = app_client.get(
        f"/api/v1/conversations/{conversation['id']}/workspace-files/preview",
        params={"path": "artifacts/notes.md"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["relative_path"] == "artifacts/notes.md"
    assert body["preview_type"] == "markdown"
    assert body["media_type"] == "text/markdown"
    assert body["content"] == "# Notes\n\nhello"


def test_user_can_preview_docx_workspace_file_as_html(
    app_client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
):
    del db_session
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    artifact = tmp_path / f"user_{user_id}" / f"conv_{conversation['id']}" / "artifacts" / "paper.docx"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"fake docx")

    class FakeSettings:
        WORKSPACE_ROOT = str(tmp_path)

    class FakeMammoth:
        @staticmethod
        def convert_to_html(file_obj):
            assert file_obj.read() == b"fake docx"
            return SimpleNamespace(value="<h1>Paper</h1>", messages=[])

    monkeypatch.setattr("backend.app.api.v1.conversations.get_settings", lambda: FakeSettings(), raising=False)
    monkeypatch.setitem(__import__("sys").modules, "mammoth", FakeMammoth)

    response = app_client.get(
        f"/api/v1/conversations/{conversation['id']}/workspace-files/preview",
        params={"path": "artifacts/paper.docx"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preview_type"] == "docx_html"
    assert body["html"] == "<h1>Paper</h1>"


def test_user_can_fetch_pdf_workspace_file_raw(
    app_client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
):
    del db_session
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)
    user_id = app_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    artifact = tmp_path / f"user_{user_id}" / f"conv_{conversation['id']}" / "artifacts" / "paper.pdf"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"%PDF-1.4\n")

    class FakeSettings:
        WORKSPACE_ROOT = str(tmp_path)

    monkeypatch.setattr("backend.app.api.v1.conversations.get_settings", lambda: FakeSettings(), raising=False)

    response = app_client.get(
        f"/api/v1/conversations/{conversation['id']}/workspace-files/raw",
        params={"path": "artifacts/paper.pdf"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content == b"%PDF-1.4\n"


def test_workspace_file_preview_rejects_unsafe_paths(
    app_client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
):
    del db_session
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    class FakeSettings:
        WORKSPACE_ROOT = str(tmp_path)

    monkeypatch.setattr("backend.app.api.v1.conversations.get_settings", lambda: FakeSettings(), raising=False)

    for unsafe_path in ("../secret.txt", "/tmp/secret.txt", "scratch/notes.txt"):
        response = app_client.get(
            f"/api/v1/conversations/{conversation['id']}/workspace-files/preview",
            params={"path": unsafe_path},
            headers=headers,
        )
        assert response.status_code == 400


def test_other_user_cannot_preview_workspace_file(
    app_client: TestClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
):
    del db_session
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)

    class FakeSettings:
        WORKSPACE_ROOT = str(tmp_path)

    monkeypatch.setattr("backend.app.api.v1.conversations.get_settings", lambda: FakeSettings(), raising=False)

    response = app_client.get(
        f"/api/v1/conversations/{conversation['id']}/workspace-files/preview",
        params={"path": "artifacts/notes.md"},
        headers=headers_b,
    )

    assert response.status_code == 404
