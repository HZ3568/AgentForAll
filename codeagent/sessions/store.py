from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4


SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
DEFAULT_TITLE = "New Chat"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_dump(value: Any) -> Any:
    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        return None
    try:
        return dump(mode="json")
    except TypeError:
        return dump()


def _to_plain(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_to_plain(item) for item in value]
    if isinstance(value, SimpleNamespace):
        return _to_plain(vars(value))
    if is_dataclass(value):
        return _to_plain(asdict(value))

    dumped = _model_dump(value)
    if dumped is not None:
        return _to_plain(dumped)

    as_dict = getattr(value, "dict", None)
    if callable(as_dict):
        return _to_plain(as_dict())

    if hasattr(value, "__dict__"):
        return _to_plain(
            {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        )

    return str(value)


def normalize_history(history: list[Any]) -> list[dict[str, Any]]:
    normalized = _to_plain(history)
    if not isinstance(normalized, list):
        return []

    messages: list[dict[str, Any]] = []
    for item in normalized:
        if isinstance(item, dict):
            role = str(item.get("role", "user"))
            messages.append({"role": role, "content": item.get("content", "")})
        else:
            messages.append({"role": "user", "content": str(item)})
    return messages


def _first_user_text(history: list[dict[str, Any]], limit: int = 48) -> str:
    for message in history:
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            text = " ".join(parts).strip()
        else:
            text = str(content).strip()
        if text:
            return text[:limit]
    return DEFAULT_TITLE


class ConversationStore:
    def __init__(self, workdir: Path) -> None:
        self.sessions_dir = workdir / ".sessions"
        self.index_path = self.sessions_dir / "index.json"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    def _ensure_index(self) -> None:
        if not self.index_path.exists():
            self.index_path.write_text(
                json.dumps({"sessions": []}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def _path(self, session_id: str) -> Path:
        if not SESSION_ID_RE.match(session_id):
            raise ValueError(f"Invalid session id: {session_id}")
        path = (self.sessions_dir / f"{session_id}.json").resolve()
        root = self.sessions_dir.resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Session path escapes sessions directory: {session_id}")
        return path

    def _metadata(self, session: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": session["id"],
            "title": session.get("title") or DEFAULT_TITLE,
            "created_at": session.get("created_at", ""),
            "updated_at": session.get("updated_at", ""),
            "message_count": int(session.get("message_count", 0)),
        }

    def rebuild_index(self) -> None:
        sessions = []
        for path in sorted(self.sessions_dir.glob("*.json")):
            if path.name == "index.json":
                continue
            try:
                sessions.append(self._metadata(json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        self.index_path.write_text(
            json.dumps({"sessions": sessions}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list(self) -> list[dict[str, Any]]:
        self._ensure_index()
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            self.rebuild_index()
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        sessions = data.get("sessions", [])
        return sessions if isinstance(sessions, list) else []

    def create(self, title: str | None = None, history: list[Any] | None = None) -> dict[str, Any]:
        session_id = f"session_{uuid4().hex}"
        normalized = normalize_history(history or [])
        now = _utc_now()
        session = {
            "id": session_id,
            "title": (title or _first_user_text(normalized)).strip() or DEFAULT_TITLE,
            "created_at": now,
            "updated_at": now,
            "message_count": len(normalized),
            "history": normalized,
        }
        self._path(session_id).write_text(
            json.dumps(session, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.rebuild_index()
        return session

    def load(self, session_id: str) -> dict[str, Any]:
        path = self._path(session_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["history"] = normalize_history(data.get("history", []))
        data["message_count"] = len(data["history"])
        return data

    def save(
        self,
        session_id: str,
        history: list[Any],
        title: str | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_history(history)
        path = self._path(session_id)
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            created_at = existing.get("created_at") or _utc_now()
            existing_title = existing.get("title") or DEFAULT_TITLE
        else:
            created_at = _utc_now()
            existing_title = ""

        session = {
            "id": session_id,
            "title": (title or existing_title or _first_user_text(normalized)).strip() or DEFAULT_TITLE,
            "created_at": created_at,
            "updated_at": _utc_now(),
            "message_count": len(normalized),
            "history": normalized,
        }
        path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
        self.rebuild_index()
        return session

    def rename(self, session_id: str, title: str) -> dict[str, Any]:
        session = self.load(session_id)
        return self.save(session_id, session["history"], title=title.strip() or DEFAULT_TITLE)

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
        self.rebuild_index()
