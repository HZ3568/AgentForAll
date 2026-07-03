from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: str


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
