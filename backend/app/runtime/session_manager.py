from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings
from backend.app.runtime.agent_adapter import AgentRuntimeAdapter
from backend.app.runtime.types import AgentTurnResult


class AgentRunConflict(RuntimeError):
    """Raised when a conversation already has an active in-process run."""


class AgentSessionManager:
    def __init__(
        self,
        adapter: AgentRuntimeAdapter | None = None,
        workspace_root: str | Path | None = None,
    ) -> None:
        self.adapter = adapter or AgentRuntimeAdapter()
        self.workspace_root = Path(workspace_root or get_settings().WORKSPACE_ROOT)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def get_lock_key(self, user_id: str, conversation_id: str) -> str:
        return f"{user_id}:{conversation_id}"

    @contextmanager
    def conversation_lock(self, user_id: str, conversation_id: str) -> Iterator[None]:
        lock = self._get_lock(self.get_lock_key(user_id, conversation_id))
        acquired = lock.acquire(blocking=False)
        if not acquired:
            raise AgentRunConflict("Conversation already has a running agent turn.")
        try:
            yield
        finally:
            lock.release()

    def run_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        history: list[dict[str, Any]],
        user_message: dict[str, Any],
    ) -> AgentTurnResult:
        with self.conversation_lock(user_id, conversation_id):
            return self.run_turn_unlocked(
                user_id=user_id,
                conversation_id=conversation_id,
                history=history,
                user_message=user_message,
            )

    def run_turn_unlocked(
        self,
        *,
        user_id: str,
        conversation_id: str,
        history: list[dict[str, Any]],
        user_message: dict[str, Any],
    ) -> AgentTurnResult:
        workspace_path = self.prepare_workspace(user_id, conversation_id)
        return self.adapter.run_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            history=history,
            user_message=user_message,
            workspace_path=str(workspace_path),
        )

    def prepare_workspace(self, user_id: str, conversation_id: str) -> Path:
        workspace = self.workspace_root / f"user_{user_id}" / f"conv_{conversation_id}"
        for child in ("scratch", "uploads", "artifacts", "traces"):
            (workspace / child).mkdir(parents=True, exist_ok=True)
        return workspace

    def _get_lock(self, key: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock


_default_session_manager: AgentSessionManager | None = None
_default_session_manager_guard = threading.Lock()


def get_default_agent_session_manager() -> AgentSessionManager:
    global _default_session_manager
    with _default_session_manager_guard:
        if _default_session_manager is None:
            _default_session_manager = AgentSessionManager()
        return _default_session_manager

