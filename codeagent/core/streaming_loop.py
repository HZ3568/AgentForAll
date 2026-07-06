from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from codeagent.core.context import (
    compact_history,
    has_tool_use,
    prepare_context,
    reactive_compact,
)
from codeagent.core.llm import RecoveryState, is_prompt_too_long_error
from codeagent.core.loop import (
    COMPACT_TOOL_NAMES,
    TODO_TOOL_NAMES,
    build_user_content,
    inject_background_notifications,
    record_tool_observation,
)
from codeagent.core.prompt import assemble_system_prompt
from codeagent.tasks.background import call_tool_handler
from codeagent.tools.results import ToolResult, is_tool_failure
from codeagent.tools.registry import build_tool_pool


@dataclass(slots=True)
class StreamingCallbacks:
    on_text_delta: Callable[[str], Any] | None = None
    on_tool_call_started: Callable[[Any], Any] | None = None
    on_tool_call_finished: Callable[[Any, str, str], Any] | None = None


def agent_loop_streaming(
    runtime: Any,
    messages: list,
    context: dict,
    callbacks: StreamingCallbacks | None = None,
) -> None:
    callbacks = callbacks or StreamingCallbacks()
    tools, handlers = build_tool_pool(runtime)
    state = RecoveryState(current_model=runtime.settings.primary_model)
    max_tokens = runtime.settings.default_max_tokens

    while True:
        for job in runtime.cron.consume():
            messages.append({"role": "user", "content": f"[Scheduled] {job.prompt}"})
            print(f"  \033[35m[cron inject] {job.prompt[:60]}\033[0m")

        inject_background_notifications(runtime, messages)

        if runtime.rounds_since_todo >= 3:
            messages.append(
                {"role": "user", "content": "<reminder>Update your todos.</reminder>"}
            )
            runtime.rounds_since_todo = 0

        memory_snapshot = runtime.memory.snapshot_messages(messages)
        prepare_context(runtime, messages)
        context.update(runtime.update_context(context, messages))
        tools, handlers = build_tool_pool(runtime)

        try:
            response = call_llm_streaming(
                runtime,
                messages,
                context,
                tools,
                state,
                max_tokens,
                callbacks,
            )
        except Exception as exc:
            if (
                is_prompt_too_long_error(exc)
                and not state.has_attempted_reactive_compact
            ):
                messages[:] = reactive_compact(runtime, messages)
                state.has_attempted_reactive_compact = True
                continue
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": f"[Error] {type(exc).__name__}: {exc}"}
                    ],
                }
            )
            return

        if response.stop_reason == "max_tokens":
            if not state.has_escalated:
                max_tokens = runtime.settings.escalated_max_tokens
                state.has_escalated = True
                continue
            messages.append({"role": "assistant", "content": response.content})
            if state.recovery_count < runtime.settings.max_recovery_retries:
                messages.append(
                    {"role": "user", "content": runtime.settings.continuation_prompt}
                )
                state.recovery_count += 1
                continue
            return

        max_tokens = runtime.settings.default_max_tokens
        state.has_escalated = False
        messages.append({"role": "assistant", "content": response.content})
        if not has_tool_use(response.content):
            extracted = runtime.memory.extract_new_memories(
                memory_snapshot,
                client=runtime.client,
                model=runtime.settings.model_id,
            )
            if extracted:
                print(f"\033[33m[Memory: extracted {extracted} new memories]\033[0m")
            consolidated = runtime.memory.consolidate_memories(
                client=runtime.client,
                model=runtime.settings.model_id,
            )
            if consolidated:
                before, after = consolidated
                print(
                    f"\033[33m[Memory: consolidated {before} -> {after} memories]\033[0m"
                )
            runtime.hooks.trigger("Stop", messages)
            return

        results: list[dict] = []
        compacted_now = False
        for block in response.content:
            if _block_value(block, "type") != "tool_use":
                continue
            tool_name = str(_block_value(block, "name") or "unknown_tool")
            print(f"\033[36m> {tool_name}\033[0m")
            if tool_name in COMPACT_TOOL_NAMES:
                messages[:] = compact_history(runtime, messages)
                messages.append(
                    {
                        "role": "user",
                        "content": "[Compacted. Continue with summarized context.]",
                    }
                )
                compacted_now = True
                break

            if callbacks.on_tool_call_started:
                callbacks.on_tool_call_started(block)

            blocked = runtime.hooks.trigger("PreToolUse", block)
            if blocked:
                output_content = record_tool_observation(runtime, tool_name, str(blocked))
                if callbacks.on_tool_call_finished:
                    callbacks.on_tool_call_finished(block, output_content, "denied")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": _block_value(block, "id"),
                        "content": output_content,
                    }
                )
                continue

            block_input = _block_value(block, "input") or {}
            if runtime.background.should_run(tool_name, block_input):
                bg_id = runtime.background.start(
                    block,
                    handlers,
                    lambda b, out: runtime.hooks.trigger("PostToolUse", b, out),
                )
                output_content = (
                    f"[Background task {bg_id} started] Result will arrive as a task_notification."
                )
                if callbacks.on_tool_call_finished:
                    callbacks.on_tool_call_finished(block, output_content, "succeeded")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": _block_value(block, "id"),
                        "content": output_content,
                    }
                )
                continue

            output = call_tool_handler(handlers.get(tool_name), block_input, tool_name)
            runtime.hooks.trigger("PostToolUse", block, output)
            output_content = record_tool_observation(runtime, tool_name, output)
            print(output_content[:300])

            if callbacks.on_tool_call_finished:
                callbacks.on_tool_call_finished(
                    block,
                    output_content,
                    _tool_status(output, output_content),
                )

            if tool_name in TODO_TOOL_NAMES:
                runtime.rounds_since_todo = 0
            else:
                runtime.rounds_since_todo += 1
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": _block_value(block, "id"),
                    "content": output_content,
                }
            )

        if compacted_now:
            continue
        messages.append({"role": "user", "content": build_user_content(runtime, results)})


def call_llm_streaming(
    runtime: Any,
    messages: list,
    context: dict,
    tools: list,
    state: RecoveryState,
    max_tokens: int,
    callbacks: StreamingCallbacks,
):
    system = assemble_system_prompt(runtime, context)
    with runtime.client.messages.stream(
        model=state.current_model,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens,
    ) as stream:
        for text in stream.text_stream:
            if text and callbacks.on_text_delta:
                callbacks.on_text_delta(text)
        return stream.get_final_message()


def _block_value(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)
    return getattr(block, key, None)


def _tool_status(output: Any, output_content: str) -> str:
    if isinstance(output, ToolResult):
        return "succeeded" if output.ok else "failed"
    failed, _ = is_tool_failure(output_content)
    return "failed" if failed else "succeeded"
