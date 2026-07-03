from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.base import utc_now
from backend.app.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_for_user(self, user_id: str, title: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title)
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def list_for_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt))

    def get_for_user(self, conversation_id: str, user_id: str) -> Conversation | None:
        return self.db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )

    def update_title_for_user(self, conversation_id: str, user_id: str, title: str) -> Conversation | None:
        conversation = self.get_for_user(conversation_id, user_id)
        if conversation is None:
            return None
        conversation.title = title
        conversation.updated_at = utc_now()
        self.db.flush()
        return conversation

    def soft_delete_for_user(self, conversation_id: str, user_id: str) -> Conversation | None:
        conversation = self.get_for_user(conversation_id, user_id)
        if conversation is None:
            return None
        conversation.status = "deleted"
        conversation.updated_at = utc_now()
        self.db.flush()
        return conversation
