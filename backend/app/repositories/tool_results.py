from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.tool_call import ToolCall
from backend.app.models.tool_result import ToolResult


class ToolResultRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_tool_result(
        self,
        user_id: str,
        tool_call_id: str,
        output_text: str | None,
        output_json: dict[str, Any] | list[Any] | None = None,
        evidence_json: dict[str, Any] | list[Any] | None = None,
        error_type: str | None = None,
    ) -> ToolResult | None:
        tool_call = self.db.scalar(
            select(ToolCall).where(
                ToolCall.id == tool_call_id,
                ToolCall.user_id == user_id,
            )
        )
        if tool_call is None:
            return None

        result = ToolResult(
            tool_call_id=tool_call_id,
            output_text=output_text,
            output_json=output_json,
            evidence_json=evidence_json,
            error_type=error_type,
        )
        self.db.add(result)
        self.db.flush()
        return result

    def get_for_tool_call(self, user_id: str, tool_call_id: str) -> ToolResult | None:
        stmt = (
            select(ToolResult)
            .join(ToolCall, ToolCall.id == ToolResult.tool_call_id)
            .where(ToolCall.user_id == user_id, ToolResult.tool_call_id == tool_call_id)
        )
        return self.db.scalar(stmt)

