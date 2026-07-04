from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.base import utc_now
from backend.app.models.tool_call import ToolCall


class ToolCallRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_tool_call(
        self,
        user_id: str,
        conversation_id: str,
        run_id: str,
        tool_name: str,
        tool_input_json: dict[str, Any] | list[Any] | None,
        status: str = "pending",
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> ToolCall:
        now = utc_now()
        call = ToolCall(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run_id,
            tool_name=tool_name,
            tool_input_json=tool_input_json if tool_input_json is not None else {},
            status=status,
            started_at=started_at or now,
            finished_at=(finished_at or now) if status in {"succeeded", "failed", "denied"} else None,
        )
        self.db.add(call)
        self.db.flush()
        return call

    def mark_finished(self, tool_call_id: str, user_id: str, status: str) -> ToolCall | None:
        call = self.get_for_user(tool_call_id, user_id)
        if call is None:
            return None
        call.status = status
        call.finished_at = utc_now()
        self.db.flush()
        return call

    def get_for_user(self, tool_call_id: str, user_id: str) -> ToolCall | None:
        return self.db.scalar(
            select(ToolCall).where(
                ToolCall.id == tool_call_id,
                ToolCall.user_id == user_id,
            )
        )

    def list_for_run(self, user_id: str, run_id: str) -> list[ToolCall]:
        stmt = (
            select(ToolCall)
            .where(ToolCall.user_id == user_id, ToolCall.run_id == run_id)
            .order_by(ToolCall.created_at.asc())
        )
        return list(self.db.scalars(stmt))
