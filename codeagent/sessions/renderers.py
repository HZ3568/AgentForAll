from __future__ import annotations

import json
from typing import Any


def _get(block: Any, key: str, default: Any = None) -> Any:
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def _text_from_tool_result(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if _get(item, "type") == "text":
                parts.append(str(_get(item, "text", "")))
            else:
                parts.append(json.dumps(_jsonable(item), ensure_ascii=False, indent=2))
        return "\n".join(part for part in parts if part)
    return json.dumps(_jsonable(content), ensure_ascii=False, indent=2)


def block_to_display(block: Any) -> dict[str, Any]:
    block_type = _get(block, "type")
    if block_type == "text":
        return {"type": "text", "text": str(_get(block, "text", ""))}
    if block_type == "tool_use":
        return {
            "type": "tool_use",
            "id": str(_get(block, "id", "")),
            "name": str(_get(block, "name", "unknown")),
            "input": _jsonable(_get(block, "input", {})),
        }
    if block_type == "tool_result":
        return {
            "type": "tool_result",
            "tool_use_id": str(_get(block, "tool_use_id", "")),
            "content": _text_from_tool_result(_get(block, "content", "")),
        }
    return {"type": "text", "text": str(block)}


def content_to_display(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, list):
        return [block_to_display(block) for block in content]
    return [{"type": "text", "text": str(content)}]


def message_to_display(message: dict[str, Any]) -> dict[str, Any]:
    blocks = content_to_display(message.get("content", ""))
    raw_role = str(message.get("role", "assistant"))
    role = raw_role if raw_role in {"user", "assistant"} else "assistant"
    if raw_role == "user" and blocks and all(block.get("type") == "tool_result" for block in blocks):
        role = "assistant"
    return {"role": role, "raw_role": raw_role, "content": blocks}


def messages_to_display(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    display_messages = []
    for message in messages:
        display_message = message_to_display(message)
        if any(
            block.get("text") or block.get("content") or block.get("name")
            for block in display_message["content"]
        ):
            display_messages.append(display_message)
    return display_messages


def export_display_messages(display_messages: list[dict[str, Any]]) -> tuple[str, str]:
    json_data = json.dumps(display_messages, ensure_ascii=False, indent=2)
    markdown_lines: list[str] = ["# AgentForAll Chat", ""]
    for message in display_messages:
        markdown_lines.append(f"## {message.get('role', 'assistant').title()}")
        for block in message.get("content", []):
            block_type = block.get("type")
            if block_type == "text":
                markdown_lines.append(str(block.get("text", "")))
            elif block_type == "tool_use":
                markdown_lines.append(f"### Tool call: {block.get('name', 'unknown')}")
                markdown_lines.append("```json")
                markdown_lines.append(json.dumps(block.get("input", {}), ensure_ascii=False, indent=2))
                markdown_lines.append("```")
            elif block_type == "tool_result":
                markdown_lines.append(f"### Tool result: {block.get('tool_use_id', 'unknown')}")
                markdown_lines.append("```text")
                markdown_lines.append(str(block.get("content", "")))
                markdown_lines.append("```")
        markdown_lines.append("")
    return json_data, "\n".join(markdown_lines)
