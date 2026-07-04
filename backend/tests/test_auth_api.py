from __future__ import annotations

from fastapi.testclient import TestClient


def register_user(client: TestClient, username: str = "alice", email: str = "alice@example.com", password: str = "password123"):
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login_user(client: TestClient, email: str = "alice@example.com", password: str = "password123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_register_success(app_client: TestClient):
    response = register_user(app_client)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert body["role"] == "user"
    assert body["status"] == "active"
    assert "password_hash" not in body


def test_register_duplicate_email_fails(app_client: TestClient):
    assert register_user(app_client).status_code == 201

    response = register_user(app_client, username="alice2", email="alice@example.com")

    assert response.status_code == 409


def test_register_duplicate_username_fails(app_client: TestClient):
    assert register_user(app_client).status_code == 201

    response = register_user(app_client, username="alice", email="alice2@example.com")

    assert response.status_code == 409


def test_login_success_returns_access_token(app_client: TestClient):
    assert register_user(app_client).status_code == 201

    response = login_user(app_client)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_returns_401(app_client: TestClient):
    assert register_user(app_client).status_code == 201

    response = login_user(app_client, password="wrong-password")

    assert response.status_code == 401


def test_auth_me_without_token_returns_401(app_client: TestClient):
    response = app_client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_auth_me_with_token_returns_current_user(app_client: TestClient):
    assert register_user(app_client).status_code == 201
    token = login_user(app_client).json()["access_token"]

    response = app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"
