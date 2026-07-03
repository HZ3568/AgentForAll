from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, IdMixin, utc_now


class RunEvent(IdMixin, Base):
    __tablename__ = "run_events"
    __table_args__ = (
        Index("ix_run_events_run_sequence_no", "run_id", "sequence_no"),
        Index("ix_run_events_conversation_created_at", "conversation_id", "created_at"),
    )

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped["AgentRun"] = relationship(back_populates="events")
    conversation: Mapped["Conversation"] = relationship(back_populates="run_events")
