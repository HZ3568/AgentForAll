from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, IdMixin, TimestampMixin


class ScheduledJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (Index("ix_scheduled_jobs_user_enabled", "user_id", "enabled"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=True)
    cron_expr: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="scheduled_jobs")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="scheduled_jobs")
