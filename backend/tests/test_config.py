from __future__ import annotations

from pathlib import Path

from backend.app.core.config import Settings


def test_cors_origins_accepts_comma_separated_env_value(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    settings = Settings()

    assert settings.CORS_ORIGINS == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_cors_origins_accepts_json_env_value(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173","http://127.0.0.1:5173"]')

    settings = Settings()

    assert settings.CORS_ORIGINS == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_backend_env_file_is_repo_root_absolute_path():
    env_file = Path(Settings.model_config["env_file"])

    assert env_file.is_absolute()
    assert env_file == Path(__file__).resolve().parents[2] / ".env"
