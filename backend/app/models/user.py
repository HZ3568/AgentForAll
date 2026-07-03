from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    messages: Mapped[list["Message"]] = relationship(back_populates="user")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="user")
    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="user")
    memories: Mapped[list["MemoryRecord"]] = relationship(back_populates="user")
    tasks: Mapped[list["TaskItem"]] = relationship(back_populates="user")
    scheduled_jobs: Mapped[list["ScheduledJob"]] = relationship(back_populates="user")
    workspace_files: Mapped[list["WorkspaceFile"]] = relationship(back_populates="user")
