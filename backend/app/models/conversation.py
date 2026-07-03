from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, IdMixin, TimestampMixin


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_updated_at", "user_id", "updated_at"),
        Index("ix_conversations_user_last_message_at", "user_id", "last_message_at"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="conversation")
    run_events: Mapped[list["RunEvent"]] = relationship(back_populates="conversation")
    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="conversation")
    memories: Mapped[list["MemoryRecord"]] = relationship(back_populates="conversation")
    tasks: Mapped[list["TaskItem"]] = relationship(back_populates="conversation")
    scheduled_jobs: Mapped[list["ScheduledJob"]] = relationship(back_populates="conversation")
    workspace_files: Mapped[list["WorkspaceFile"]] = relationship(back_populates="conversation")
