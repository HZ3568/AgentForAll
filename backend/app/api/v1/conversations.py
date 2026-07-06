from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
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
    WorkspaceFilePreviewResponse,
    WorkspaceFileRead,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

ALLOWED_WORKSPACE_SECTIONS = ("uploads", "artifacts", "traces")
MAX_TEXT_PREVIEW_BYTES = 2 * 1024 * 1024
MAX_DOCX_PREVIEW_BYTES = 10 * 1024 * 1024

MARKDOWN_EXTENSIONS = {".md", ".markdown"}
TEXT_EXTENSIONS = {
    ".csv",
    ".css",
    ".html",
    ".js",
    ".json",
    ".log",
    ".py",
    ".rst",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}


def datetime_from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)


def workspace_root_for_user_conversation(user_id: str, conversation_id: str) -> Path:
    return Path(get_settings().WORKSPACE_ROOT).resolve() / f"user_{user_id}" / f"conv_{conversation_id}"


def guess_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in MARKDOWN_EXTENSIONS:
        return "text/markdown"
    media_type, _ = mimetypes.guess_type(path.name)
    if media_type:
        return media_type
    if suffix in TEXT_EXTENSIONS:
        return "text/plain"
    return "application/octet-stream"


def validate_workspace_relative_path(raw_path: str) -> PurePosixPath:
    normalized = raw_path.replace("\\", "/").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path is required.")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or any(part in ("", ".", "..") or ":" in part for part in relative.parts):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsafe workspace file path.")
    if relative.parts[0] not in ALLOWED_WORKSPACE_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace file section is not allowed.")
    return relative


def resolve_workspace_file(
    conversation_id: str,
    current_user: User,
    db: Session,
    raw_path: str,
) -> tuple[Path, str]:
    if ConversationRepository(db).get_active_for_user(conversation_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    relative = validate_workspace_relative_path(raw_path)
    workspace = workspace_root_for_user_conversation(current_user.id, conversation_id)
    section_root = (workspace / relative.parts[0]).resolve()
    resolved = (workspace / Path(*relative.parts)).resolve()
    if not resolved.is_relative_to(section_root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsafe workspace file path.")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace file not found.")
    return resolved, relative.as_posix()


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

    workspace = workspace_root_for_user_conversation(current_user.id, conversation_id)
    items: list[WorkspaceFileRead] = []
    for section in ALLOWED_WORKSPACE_SECTIONS:
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


@router.get("/{conversation_id}/workspace-files/preview", response_model=WorkspaceFilePreviewResponse)
def preview_workspace_file(
    conversation_id: str,
    path: Annotated[str, Query(min_length=1)],
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceFilePreviewResponse:
    resolved, relative_path = resolve_workspace_file(conversation_id, current_user, db, path)
    stat = resolved.stat()
    suffix = resolved.suffix.lower()
    media_type = guess_media_type(resolved)

    if suffix in MARKDOWN_EXTENSIONS | TEXT_EXTENSIONS:
        if stat.st_size > MAX_TEXT_PREVIEW_BYTES:
            return WorkspaceFilePreviewResponse(
                relative_path=relative_path,
                filename=resolved.name,
                preview_type="download_only",
                media_type=media_type,
                size_bytes=stat.st_size,
                error_message="File is too large to preview inline.",
            )
        preview_type = "markdown" if suffix in MARKDOWN_EXTENSIONS else "text"
        return WorkspaceFilePreviewResponse(
            relative_path=relative_path,
            filename=resolved.name,
            preview_type=preview_type,
            media_type=media_type,
            content=resolved.read_text(encoding="utf-8"),
            size_bytes=stat.st_size,
        )

    if suffix in PDF_EXTENSIONS:
        return WorkspaceFilePreviewResponse(
            relative_path=relative_path,
            filename=resolved.name,
            preview_type="pdf",
            media_type=media_type,
            size_bytes=stat.st_size,
        )

    if suffix in IMAGE_EXTENSIONS:
        return WorkspaceFilePreviewResponse(
            relative_path=relative_path,
            filename=resolved.name,
            preview_type="image",
            media_type=media_type,
            size_bytes=stat.st_size,
        )

    if suffix in DOCX_EXTENSIONS:
        if stat.st_size > MAX_DOCX_PREVIEW_BYTES:
            return WorkspaceFilePreviewResponse(
                relative_path=relative_path,
                filename=resolved.name,
                preview_type="download_only",
                media_type=media_type,
                size_bytes=stat.st_size,
                error_message="DOCX file is too large to preview inline.",
            )
        try:
            import mammoth

            with resolved.open("rb") as file_obj:
                result = mammoth.convert_to_html(file_obj)
        except Exception as exc:  # pragma: no cover - exact provider errors vary.
            return WorkspaceFilePreviewResponse(
                relative_path=relative_path,
                filename=resolved.name,
                preview_type="download_only",
                media_type=media_type,
                size_bytes=stat.st_size,
                error_message=f"DOCX preview failed: {exc}",
            )
        return WorkspaceFilePreviewResponse(
            relative_path=relative_path,
            filename=resolved.name,
            preview_type="docx_html",
            media_type=media_type,
            html=result.value,
            size_bytes=stat.st_size,
        )

    return WorkspaceFilePreviewResponse(
        relative_path=relative_path,
        filename=resolved.name,
        preview_type="download_only",
        media_type=media_type,
        size_bytes=stat.st_size,
    )


@router.get("/{conversation_id}/workspace-files/raw")
def get_workspace_file_raw(
    conversation_id: str,
    path: Annotated[str, Query(min_length=1)],
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    resolved, _ = resolve_workspace_file(conversation_id, current_user, db, path)
    return FileResponse(
        resolved,
        filename=resolved.name,
        media_type=guess_media_type(resolved),
    )


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
