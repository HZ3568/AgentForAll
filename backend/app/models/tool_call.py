from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, IdMixin, utc_now


class ToolCall(IdMixin, Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("ix_tool_calls_run_created_at", "run_id", "created_at"),
        Index("ix_tool_calls_user_tool_name", "user_id", "tool_name"),
    )

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_input_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped["AgentRun"] = relationship(back_populates="tool_calls")
    conversation: Mapped["Conversation"] = relationship(back_populates="tool_calls")
    user: Mapped["User"] = relationship(back_populates="tool_calls")
    result: Mapped["ToolResult | None"] = relationship(back_populates="tool_call", uselist=False)
