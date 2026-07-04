from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from backend.app.runtime.types import (
    AgentEventRecord,
    AgentToolCallRecord,
    AgentToolResultRecord,
    AgentTurnResult,
)
from codeagent.core.loop import agent_loop
from codeagent.core.runtime import create_runtime


RuntimeFactory = Callable[[str | None], Any]
LoopRunner = Callable[[Any, list[dict[str, Any]], dict[str, Any]], None]


class AgentRuntimeAdapter:
    """Adapts persisted backend messages to codeagent's in-place agent loop."""

    def __init__(
        self,
        runtime_factory: RuntimeFactory | None = None,
        loop_runner: LoopRunner | None = None,
    ) -> None:
        self._runtime_factory = runtime_factory or create_runtime
        self._loop_runner = loop_runner or agent_loop

    def run_turn(
        self,
        *,
        conversation_id: str,
        user_id: str,
        history: list[dict[str, Any]],
        user_message: dict[str, Any],
        workspace_path: str | None = None,
    ) -> AgentTurnResult:
        del conversation_id, user_id
        messages = [self._to_codeagent_message(message) for message in history]
        messages.append(self._to_codeagent_message(user_message))
        turn_start = len(messages)

        try:
            runtime = self._create_runtime(workspace_path)
            runtime.reset_tool_tracking()
            runtime.current_scratch_dir = (
                str(Path(workspace_path) / "scratch") if workspace_path else None
            )
            context = runtime.update_context({}, messages)
            self._loop_runner(runtime, messages, context)
        except Exception as exc:
            return AgentTurnResult(
                events=[
                    AgentEventRecord(
                        event_type="run_failed",
                        event_json={"error_type": type(exc).__name__, "message": str(exc)},
                    )
                ],
                error=f"{type(exc).__name__}: {exc}",
            )

        new_messages = messages[turn_start:]
        return self._collect_result(new_messages)

    def _create_runtime(self, workspace_path: str | None) -> Any:
        if workspace_path is None:
            return self._runtime_factory(None)

        workspace = Path(workspace_path)
        workspace.mkdir(parents=True, exist_ok=True)
        config_path = workspace / "codeagent_web_config.yaml"
        config_path.write_text(
            yaml.safe_dump({"workdir": str(workspace)}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return self._runtime_factory(str(config_path))

    def _to_codeagent_message(self, message: dict[str, Any]) -> dict[str, Any]:
        role = str(message.get("role") or "user")
        content_json = message.get("content_json")
        content_text = message.get("content_text")

        if isinstance(content_json, dict) and content_json.get("type") == "text":
            content = str(content_json.get("text") or content_text or "")
        elif isinstance(content_json, str):
            content = content_json
        elif content_text:
            content = str(content_text)
        elif isinstance(content_json, list):
            content = content_json
        else:
            content = ""
        return {"role": role, "content": content}

    def _collect_result(self, new_messages: list[dict[str, Any]]) -> AgentTurnResult:
        assistant_messages: list[dict[str, Any]] = []
        events: list[AgentEventRecord] = []
        tool_calls: list[AgentToolCallRecord] = []
        tool_results: list[AgentToolResultRecord] = []
        final_text: str | None = None

        for message in new_messages:
            role = message.get("role")
            content = message.get("content")
            if role == "assistant":
                content_json = self._jsonable_content(content)
                content_text = self._content_text(content)
                assistant_messages.append(
                    {
                        "role": "assistant",
                        "content_json": content_json,
                        "content_text": content_text,
                    }
                )
                if content_text:
                    final_text = content_text
                events.append(
                    AgentEventRecord(
                        event_type="message_created",
                        event_json={"role": "assistant", "text": content_text[:1000]},
                    )
                )
                tool_calls.extend(self._extract_tool_calls(content))
            elif role == "user":
                extracted_results = self._extract_tool_results(content)
                if extracted_results:
                    tool_results.extend(extracted_results)

        return AgentTurnResult(
            assistant_messages=assistant_messages,
            events=events,
            tool_calls=tool_calls,
            tool_results=tool_results,
            final_text=final_text,
        )

    def _extract_tool_calls(self, content: Any) -> list[AgentToolCallRecord]:
        records: list[AgentToolCallRecord] = []
        for block in self._iter_blocks(content):
            if self._block_value(block, "type") != "tool_use":
                continue
            records.append(
                AgentToolCallRecord(
                    external_id=self._string_or_none(self._block_value(block, "id")),
                    tool_name=str(self._block_value(block, "name") or "unknown_tool"),
                    tool_input_json=self._jsonable_content(self._block_value(block, "input") or {}),
                    status="succeeded",
                )
            )
        return records

    def _extract_tool_results(self, content: Any) -> list[AgentToolResultRecord]:
        records: list[AgentToolResultRecord] = []
        for block in self._iter_blocks(content):
            if self._block_value(block, "type") != "tool_result":
                continue
            output = self._block_value(block, "content")
            output_text = self._content_text(output)
            records.append(
                AgentToolResultRecord(
                    tool_call_external_id=self._string_or_none(
                        self._block_value(block, "tool_use_id")
                    ),
                    output_text=output_text,
                    output_json=self._jsonable_content(block),
                    error_type=self._detect_error_type(output_text),
                )
            )
        return records

    def _iter_blocks(self, content: Any) -> list[Any]:
        if isinstance(content, list):
            return content
        return []

    def _block_value(self, block: Any, key: str) -> Any:
        if isinstance(block, dict):
            return block.get(key)
        return getattr(block, key, None)

    def _content_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if self._block_value(block, "type") == "text":
                    parts.append(str(self._block_value(block, "text") or ""))
                elif self._block_value(block, "type") == "tool_result":
                    parts.append(str(self._block_value(block, "content") or ""))
            return "\n".join(part for part in parts if part)
        if isinstance(content, dict):
            if content.get("type") == "text":
                return str(content.get("text") or "")
            return json.dumps(content, ensure_ascii=False)
        return str(content)

    def _jsonable_content(self, content: Any) -> Any:
        if isinstance(content, list):
            return [self._jsonable_content(item) for item in content]
        if isinstance(content, dict):
            return {str(key): self._jsonable_content(value) for key, value in content.items()}
        if isinstance(content, (str, int, float, bool)) or content is None:
            return content
        if hasattr(content, "model_dump"):
            return self._jsonable_content(content.model_dump())
        if hasattr(content, "__dict__"):
            return self._jsonable_content(vars(content))
        return str(content)

    def _string_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def _detect_error_type(self, output_text: str) -> str | None:
        lowered = output_text.lower()
        if "[error]" in lowered or "traceback" in lowered or "failed" in lowered:
            return "tool_error"
        return None

