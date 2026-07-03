from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, IdMixin, utc_now


class ToolResult(IdMixin, Base):
    __tablename__ = "tool_results"

    tool_call_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tool_calls.id"),
        unique=True,
        nullable=False,
    )
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tool_call: Mapped["ToolCall"] = relationship(back_populates="result")
