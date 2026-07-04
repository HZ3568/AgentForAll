from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("Content cannot be empty.")
        return content


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    user_id: str
    role: str
    content_json: dict[str, Any] | list[Any] | str | None
    content_text: str
    token_count: int | None = None
    sequence_no: int
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageRead]
