from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, IdMixin, utc_now


class AgentRun(IdMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_conversation_created_at", "conversation_id", "created_at"),
        Index("ix_agent_runs_user_status", "user_id", "status"),
    )

    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    input_message_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("messages.id"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="agent_runs")
    user: Mapped["User"] = relationship(back_populates="agent_runs")
    input_message: Mapped["Message | None"] = relationship(
        back_populates="input_for_runs",
        foreign_keys=[input_message_id],
    )
    events: Mapped[list["RunEvent"]] = relationship(back_populates="run")
    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="run")
