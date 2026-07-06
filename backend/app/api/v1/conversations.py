from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.deps import require_active_user
from backend.app.models.conversation import Conversation
from backend.app.repositories.agent_runs import AgentRunRepository
from backend.app.models.user import User
from backend.app.repositories.conversations import ConversationRepository
from backend.app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationRead,
    ConversationUpdate,
    MemoryIndexResponse,
    WorkspaceFileListResponse,
    WorkspaceFileRead,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def datetime_from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConversationListResponse:
    conversations = ConversationRepository(db).list_for_user(current_user.id, limit=limit, offset=offset)
    return ConversationListResponse(items=conversations)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Conversation:
    conversation = ConversationRepository(db).create_for_user(current_user.id, payload.title)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Conversation:
    conversation = ConversationRepository(db).get_active_for_user(conversation_id, current_user.id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conversation


@router.patch("/{conversation_id}", response_model=ConversationRead)
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Conversation:
    repo = ConversationRepository(db)
    if repo.get_active_for_user(conversation_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    conversation = repo.update_title_for_user(conversation_id, current_user.id, payload.title)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}/workspace-files", response_model=WorkspaceFileListResponse)
def list_workspace_files(
    conversation_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceFileListResponse:
    if ConversationRepository(db).get_active_for_user(conversation_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    workspace = (
        Path(get_settings().WORKSPACE_ROOT).resolve()
        / f"user_{current_user.id}"
        / f"conv_{conversation_id}"
    )
    allowed_sections = ("uploads", "artifacts", "traces")
    items: list[WorkspaceFileRead] = []
    for section in allowed_sections:
        section_root = (workspace / section).resolve()
        if not section_root.exists() or not section_root.is_dir():
            continue
        for path in sorted(section_root.rglob("*")):
            resolved = path.resolve()
            if not resolved.is_file() or not resolved.is_relative_to(section_root):
                continue
            stat = resolved.stat()
            relative_path = resolved.relative_to(workspace).as_posix()
            items.append(
                WorkspaceFileRead(
                    relative_path=relative_path,
                    section=section,
                    filename=resolved.name,
                    size_bytes=stat.st_size,
                    updated_at=datetime_from_timestamp(stat.st_mtime),
                )
            )
    return WorkspaceFileListResponse(items=items)


@router.get("/{conversation_id}/memory-index", response_model=MemoryIndexResponse)
def get_memory_index(
    conversation_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MemoryIndexResponse:
    if ConversationRepository(db).get_active_for_user(conversation_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    memory_index = (
        Path(get_settings().WORKSPACE_ROOT).resolve()
        / f"user_{current_user.id}"
        / ".memory"
        / "MEMORY.md"
    )
    if not memory_index.exists() or not memory_index.is_file():
        return MemoryIndexResponse(content=None)
    memory_root = memory_index.parent.resolve()
    resolved = memory_index.resolve()
    if not resolved.is_relative_to(memory_root):
        return MemoryIndexResponse(content=None)
    return MemoryIndexResponse(content=resolved.read_text(encoding="utf-8"))


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    repo = ConversationRepository(db)
    if repo.get_active_for_user(conversation_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    if AgentRunRepository(db).list_active_for_conversation(current_user.id, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation has an active run.",
        )
    repo.soft_delete_for_user(conversation_id, current_user.id)
    db.commit()
