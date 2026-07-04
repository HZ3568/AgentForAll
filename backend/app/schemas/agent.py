from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.message import MessageRead


class AgentTurnRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("Content cannot be empty.")
        return content


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AgentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    event_json: dict[str, Any] | list[Any] | None
    sequence_no: int
    created_at: datetime


class AgentToolCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tool_name: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AgentTurnResponse(BaseModel):
    run_id: str
    status: str
    conversation_id: str
    user_message: MessageRead
    assistant_messages: list[MessageRead]
    events: list[AgentEventRead]
    tool_calls: list[AgentToolCallRead]
    error: str | None = None

