from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from codeagent.core.streaming_loop import StreamingCallbacks, agent_loop_streaming
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


WEB_SEARCH_REQUIRED_PREFIX = (
    "<web_search_required>\n"
    "本轮用户已开启网页搜索。必须先调用 web_search 检索当前用户问题，再基于搜索结果回答。"
    "如果 web_search 不可用、失败或结果不足，明确说明失败原因和无法确认的范围，不要编造实时信息。\n"
    "</web_search_required>\n\n"
    "用户原始问题：\n"
)


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
        memory_path: str | None = None,
        web_search_enabled: bool = False,
    ) -> AgentTurnResult:
        del conversation_id, user_id
        messages = [self._to_codeagent_message(message) for message in history]
        messages.append(
            self._with_web_search_instruction(
                self._to_codeagent_message(user_message),
                web_search_enabled,
            )
        )
        original_message_ids = self._message_identity_snapshot(messages)

        try:
            runtime = self._create_runtime(workspace_path, memory_path)
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

        new_messages = self._collect_new_messages(messages, original_message_ids)
        return self._collect_result(new_messages)

    def run_turn_streaming(
        self,
        *,
        conversation_id: str,
        user_id: str,
        history: list[dict[str, Any]],
        user_message: dict[str, Any],
        workspace_path: str | None = None,
        memory_path: str | None = None,
        on_event: Callable[[AgentEventRecord], None] | None = None,
        on_tool_call: Callable[[AgentToolCallRecord], None] | None = None,
        on_tool_result: Callable[[AgentToolResultRecord], None] | None = None,
        web_search_enabled: bool = False,
    ) -> AgentTurnResult:
        del conversation_id, user_id
        messages = [self._to_codeagent_message(message) for message in history]
        messages.append(
            self._with_web_search_instruction(
                self._to_codeagent_message(user_message),
                web_search_enabled,
            )
        )
        original_message_ids = self._message_identity_snapshot(messages)
        streamed_events: list[AgentEventRecord] = []
        streamed_tool_calls: list[AgentToolCallRecord] = []
        streamed_tool_results: list[AgentToolResultRecord] = []
        delta_buffer: list[str] = []
        streamed_text_parts: list[str] = []
        last_flush = time.monotonic()

        def emit_event(event: AgentEventRecord) -> None:
            streamed_events.append(event)
            if on_event:
                on_event(event)

        def flush_delta(force: bool = False) -> None:
            nonlocal last_flush
            if not delta_buffer:
                return
            text = "".join(delta_buffer)
            elapsed = time.monotonic() - last_flush
            if not force and len(text) < 120 and elapsed < 0.2 and "\n" not in text:
                return
            delta_buffer.clear()
            last_flush = time.monotonic()
            emit_event(
                AgentEventRecord(
                    event_type="assistant_delta",
                    event_json={"role": "assistant", "delta": text},
                )
            )

        def on_text_delta(delta: str) -> None:
            streamed_text_parts.append(delta)
            delta_buffer.append(delta)
            flush_delta()

        def on_tool_call_started(block: Any) -> None:
            flush_delta(force=True)
            record = AgentToolCallRecord(
                external_id=self._string_or_none(self._block_value(block, "id")),
                tool_name=str(self._block_value(block, "name") or "unknown_tool"),
                tool_input_json=self._jsonable_content(self._block_value(block, "input") or {}),
                status="running",
            )
            if on_tool_call:
                on_tool_call(record)

        def on_tool_call_finished(block: Any, output_text: str, status: str) -> None:
            record = AgentToolCallRecord(
                external_id=self._string_or_none(self._block_value(block, "id")),
                tool_name=str(self._block_value(block, "name") or "unknown_tool"),
                tool_input_json=self._jsonable_content(self._block_value(block, "input") or {}),
                status=status,
            )
            streamed_tool_calls.append(record)
            if on_tool_call:
                on_tool_call(record)
            result_record = AgentToolResultRecord(
                tool_call_external_id=record.external_id,
                output_text=output_text,
                output_json={"content": output_text},
                error_type=self._tool_error_type_for_status(status, output_text),
            )
            streamed_tool_results.append(result_record)
            if on_tool_result:
                on_tool_result(result_record)

        try:
            runtime = self._create_runtime(workspace_path, memory_path)
            runtime.reset_tool_tracking()
            runtime.current_scratch_dir = (
                str(Path(workspace_path) / "scratch") if workspace_path else None
            )
            context = runtime.update_context({}, messages)
            agent_loop_streaming(
                runtime,
                messages,
                context,
                StreamingCallbacks(
                    on_text_delta=on_text_delta,
                    on_tool_call_started=on_tool_call_started,
                    on_tool_call_finished=on_tool_call_finished,
                ),
            )
            flush_delta(force=True)
        except Exception as exc:
            flush_delta(force=True)
            return AgentTurnResult(
                events=[
                    *streamed_events,
                    AgentEventRecord(
                        event_type="run_failed",
                        event_json={"error_type": type(exc).__name__, "message": str(exc)},
                    ),
                ],
                tool_calls=streamed_tool_calls,
                tool_results=streamed_tool_results,
                error=f"{type(exc).__name__}: {exc}",
            )

        new_messages = self._collect_new_messages(messages, original_message_ids)
        result = self._collect_result(new_messages)
        if not result.assistant_messages:
            result = self._with_streamed_text_fallback(result, "".join(streamed_text_parts))
        result.events = streamed_events
        result.tool_calls = streamed_tool_calls
        result.tool_results = streamed_tool_results
        return result

    def _message_identity_snapshot(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        return tuple(messages)

    def _collect_new_messages(
        self,
        messages: list[dict[str, Any]],
        original_messages: tuple[dict[str, Any], ...],
    ) -> list[dict[str, Any]]:
        return [
            message
            for message in messages
            if not any(message is original for original in original_messages)
        ]

    def _with_streamed_text_fallback(
        self,
        result: AgentTurnResult,
        streamed_text: str,
    ) -> AgentTurnResult:
        if not streamed_text.strip():
            return result
        result.assistant_messages = [
            {
                "role": "assistant",
                "content_json": {"type": "text", "text": streamed_text},
                "content_text": streamed_text,
            }
        ]
        result.final_text = streamed_text
        return result

    def _create_runtime(self, workspace_path: str | None, memory_path: str | None = None) -> Any:
        if workspace_path is None:
            return self._runtime_factory(None)

        workspace = Path(workspace_path)
        workspace.mkdir(parents=True, exist_ok=True)
        memory = Path(memory_path) if memory_path else workspace / ".memory"
        memory.mkdir(parents=True, exist_ok=True)
        config_path = workspace / "codeagent_web_config.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "workdir": str(workspace),
                    "memory_dir": str(memory),
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return self._runtime_factory(str(config_path))

    def _with_web_search_instruction(
        self,
        message: dict[str, Any],
        enabled: bool,
    ) -> dict[str, Any]:
        if not enabled:
            return message
        content = message.get("content")
        if isinstance(content, str):
            return {**message, "content": WEB_SEARCH_REQUIRED_PREFIX + content}
        if isinstance(content, list):
            return {
                **message,
                "content": [
                    {"type": "text", "text": WEB_SEARCH_REQUIRED_PREFIX.strip()},
                    *content,
                ],
            }
        return {**message, "content": WEB_SEARCH_REQUIRED_PREFIX + str(content or "")}

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
                        event_type="assistant_delta",
                        event_json={"role": "assistant", "delta": content_text[:1000]},
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

    def _tool_error_type_for_status(self, status: str, output_text: str) -> str | None:
        if status == "denied":
            return "permission_denied"
        if status == "failed":
            return self._detect_error_type(output_text) or "tool_error"
        return None
