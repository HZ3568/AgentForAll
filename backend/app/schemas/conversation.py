from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Title cannot be empty.")
        return title


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Title cannot be empty.")
        return title


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None


class ConversationListResponse(BaseModel):
    items: list[ConversationRead]


class WorkspaceFileRead(BaseModel):
    relative_path: str
    section: str
    filename: str
    size_bytes: int
    updated_at: datetime


class WorkspaceFileListResponse(BaseModel):
    items: list[WorkspaceFileRead]


class WorkspaceFilePreviewResponse(BaseModel):
    relative_path: str
    filename: str
    preview_type: Literal["text", "markdown", "docx_html", "pdf", "image", "download_only"]
    media_type: str | None = None
    content: str | None = None
    html: str | None = None
    size_bytes: int
    error_message: str | None = None


class MemoryIndexResponse(BaseModel):
    content: str | None = None
