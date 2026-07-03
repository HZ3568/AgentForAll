from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    role: str
    content_json: dict[str, Any] | list[Any] | str
    content_text: str


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
