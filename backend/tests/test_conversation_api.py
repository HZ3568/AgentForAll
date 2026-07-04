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
