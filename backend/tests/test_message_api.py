from __future__ import annotations

from fastapi.testclient import TestClient


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
    response = client.post("/api/v1/conversations", json={"title": "Messages"}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_user_can_create_message_in_own_conversation(app_client: TestClient):
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    response = app_client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "你好"},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "user"
    assert body["content_text"] == "你好"
    assert body["content_json"] == {"type": "text", "text": "你好"}
    assert body["sequence_no"] == 1


def test_other_user_cannot_create_message_in_conversation(app_client: TestClient):
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)

    response = app_client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "No access"},
        headers=headers_b,
    )

    assert response.status_code == 404


def test_other_user_cannot_read_messages(app_client: TestClient):
    headers_a = auth_headers(app_client, "alice", "alice@example.com")
    headers_b = auth_headers(app_client, "bob", "bob@example.com")
    conversation = create_conversation(app_client, headers_a)
    assert app_client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "secret"},
        headers=headers_a,
    ).status_code == 201

    response = app_client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=headers_b)

    assert response.status_code == 404


def test_messages_sequence_number_increments(app_client: TestClient):
    headers = auth_headers(app_client, "alice", "alice@example.com")
    conversation = create_conversation(app_client, headers)

    first = app_client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "first"},
        headers=headers,
    )
    second = app_client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "second"},
        headers=headers,
    )
    list_response = app_client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=headers)

    assert first.json()["sequence_no"] == 1
    assert second.json()["sequence_no"] == 2
    assert [item["sequence_no"] for item in list_response.json()["items"]] == [1, 2]
