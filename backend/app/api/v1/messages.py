from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import require_active_user
from backend.app.models.message import Message
from backend.app.models.user import User
from backend.app.repositories.conversations import ConversationRepository
from backend.app.repositories.messages import ConversationOwnershipError, MessageRepository
from backend.app.schemas.message import MessageCreate, MessageListResponse, MessageRead

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["messages"])


@router.get("", response_model=MessageListResponse)
def list_messages(
    conversation_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MessageListResponse:
    if ConversationRepository(db).get_active_for_user(conversation_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    messages = MessageRepository(db).list_for_conversation(current_user.id, conversation_id, limit=limit, offset=offset)
    return MessageListResponse(items=messages)


@router.post("", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def create_message(
    conversation_id: str,
    payload: MessageCreate,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Message:
    try:
        message = MessageRepository(db).create_user_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            content=payload.content,
        )
    except ConversationOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc

    db.commit()
    db.refresh(message)
    return message
