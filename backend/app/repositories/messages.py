from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.base import utc_now
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.repositories.conversations import ConversationRepository


class ConversationOwnershipError(PermissionError):
    """Raised when a repository write targets another user's conversation."""


class MessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content_json: dict[str, Any] | list[Any] | str,
        content_text: str,
        sequence_no: int | None = None,
    ) -> Message:
        conversation = ConversationRepository(self.db).get_for_user(conversation_id, user_id)
        if conversation is None:
            raise ConversationOwnershipError(
                f"Conversation {conversation_id} does not belong to user {user_id}."
            )

        next_sequence_no = sequence_no
        if next_sequence_no is None:
            next_sequence_no = self.get_next_sequence_no(user_id, conversation_id)

        now = utc_now()
        message = Message(
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content_json=content_json,
            content_text=content_text,
            sequence_no=next_sequence_no,
            created_at=now,
        )
        conversation.last_message_at = now
        conversation.updated_at = now
        self.db.add(message)
        self.db.flush()
        return message

    def list_for_conversation(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        if not self._conversation_exists_for_user(user_id, conversation_id):
            return []
        stmt = (
            select(Message)
            .where(
                Message.user_id == user_id,
                Message.conversation_id == conversation_id,
            )
            .order_by(Message.sequence_no.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt))

    def get_next_sequence_no(self, user_id: str, conversation_id: str) -> int:
        if not self._conversation_exists_for_user(user_id, conversation_id):
            raise ConversationOwnershipError(
                f"Conversation {conversation_id} does not belong to user {user_id}."
            )
        current_max = self.db.scalar(
            select(func.max(Message.sequence_no)).where(
                Message.user_id == user_id,
                Message.conversation_id == conversation_id,
            )
        )
        return int(current_max or 0) + 1

    def _conversation_exists_for_user(self, user_id: str, conversation_id: str) -> bool:
        return (
            self.db.scalar(
                select(Conversation.id).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                )
            )
            is not None
        )
