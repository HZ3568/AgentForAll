from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AgentEventRecord:
    event_type: str
    event_json: dict[str, Any] | list[Any] | None = field(default_factory=dict)
    sequence_no: int | None = None


@dataclass(slots=True)
class AgentToolCallRecord:
    tool_name: str
    tool_input_json: dict[str, Any] | list[Any] | None = field(default_factory=dict)
    status: str = "succeeded"
    external_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(slots=True)
class AgentToolResultRecord:
    tool_call_external_id: str | None = None
    output_text: str | None = None
    output_json: dict[str, Any] | list[Any] | None = None
    evidence_json: dict[str, Any] | list[Any] | None = None
    error_type: str | None = None


@dataclass(slots=True)
class AgentTurnResult:
    assistant_messages: list[dict[str, Any]] = field(default_factory=list)
    events: list[AgentEventRecord] = field(default_factory=list)
    tool_calls: list[AgentToolCallRecord] = field(default_factory=list)
    tool_results: list[AgentToolResultRecord] = field(default_factory=list)
    final_text: str | None = None
    error: str | None = None

