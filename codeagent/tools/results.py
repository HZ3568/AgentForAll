from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class FailureType(str, Enum):
    WEB_SEARCH_BLOCKED = "web_search_blocked"
    WEB_SEARCH_EMPTY = "web_search_empty"
    FETCH_FAILED = "fetch_failed"
    FILE_PARSE_FAILED = "file_parse_failed"
    AUDIO_TRANSCRIPTION_FAILED = "audio_transcription_failed"
    OCR_FAILED = "ocr_failed"
    SHELL_COMMAND_FAILED = "shell_command_failed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ANSWER_FORMAT_ERROR = "answer_format_error"
    REASONING_ERROR = "reasoning_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str | None = None


@dataclass
class EvidenceItem:
    tool_name: str
    source: str | None
    summary: str
    quote: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    ok: bool
    content: str
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence: list[EvidenceItem] = field(default_factory=list)

    def __str__(self) -> str:
        return format_tool_result(self)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        return data


FAILURE_PATTERNS: list[tuple[str, str]] = [
    ("captcha_blocked", "unfortunately, bots use duckduckgo too"),
    ("captcha_blocked", "please complete the following challenge"),
    ("captcha_blocked", "captcha"),
    ("http_403", "http 403"),
    ("http_403", "403 forbidden"),
    ("http_403", "forbidden"),
    ("http_429", "http 429"),
    ("rate_limited", "rate limited"),
    ("rate_limited", "too many requests"),
    ("access_denied", "access denied"),
    ("empty_search_results", "no search results parsed"),
]


def classify_http_error(status_code: int) -> str | None:
    if status_code == 403:
        return "http_403"
    if status_code == 429:
        return "rate_limited"
    if 400 <= status_code < 600:
        return f"http_{status_code}"
    return None


def is_tool_failure(result: str | ToolResult) -> tuple[bool, str | None]:
    if isinstance(result, ToolResult):
        return (not result.ok, result.error_type)

    text = str(result or "").lower()
    if text.startswith("error:"):
        return True, "tool_error"
    if "exit_code:" in text:
        return True, "shell_command_failed"
    for error_type, pattern in FAILURE_PATTERNS:
        if pattern in text:
            return True, error_type
    return False, None


def format_tool_result(result: Any) -> str:
    if not isinstance(result, ToolResult):
        return str(result)

    header = {
        "ok": result.ok,
        "error_type": result.error_type,
        "metadata": result.metadata,
    }
    lines = ["<tool_result>", json.dumps(header, ensure_ascii=False), result.content]
    if result.evidence:
        lines.append("<evidence>")
        for item in result.evidence:
            lines.append(json.dumps(item.to_dict(), ensure_ascii=False))
        lines.append("</evidence>")
    lines.append("</tool_result>")
    return "\n".join(lines)


def summarize_text(text: str, max_chars: int = 240) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def first_quote(text: str, max_chars: int = 500) -> str | None:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if not compact:
        return None
    return compact[:max_chars]
