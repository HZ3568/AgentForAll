from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, IdMixin, utc_now


class Message(IdMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_sequence_no", "conversation_id", "sequence_no"),
        Index("ix_messages_user_created_at", "user_id", "created_at"),
    )

    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content_json: Mapped[dict[str, Any] | list[Any] | str | None] = mapped_column(JSON, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="messages")
    input_for_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="input_message",
        foreign_keys="AgentRun.input_message_id",
    )
