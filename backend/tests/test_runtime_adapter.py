from __future__ import annotations

from typing import Any

from backend.app.runtime.agent_adapter import AgentRuntimeAdapter


class FakeRuntime:
    def __init__(self) -> None:
        self.current_scratch_dir = None

    def reset_tool_tracking(self) -> None:
        return None

    def update_context(self, context: dict | None = None, messages: list | None = None) -> dict:
        del context, messages
        return {}


def test_runtime_adapter_collects_assistant_message(tmp_path):
    def fake_loop(runtime: Any, messages: list[dict[str, Any]], context: dict[str, Any]) -> None:
        del runtime, context
        messages.append({"role": "assistant", "content": [{"type": "text", "text": "hello"}]})

    adapter = AgentRuntimeAdapter(
        runtime_factory=lambda config_path: FakeRuntime(),
        loop_runner=fake_loop,
    )

    result = adapter.run_turn(
        conversation_id="conv-1",
        user_id="user-1",
        history=[],
        user_message={"role": "user", "content_json": {"type": "text", "text": "hi"}},
        workspace_path=str(tmp_path),
    )

    assert result.error is None
    assert result.final_text == "hello"
    assert result.assistant_messages[0]["content_text"] == "hello"
    assert result.events[0].event_type == "assistant_delta"


def test_runtime_adapter_collects_tool_calls_and_results(tmp_path):
    def fake_loop(runtime: Any, messages: list[dict[str, Any]], context: dict[str, Any]) -> None:
        del runtime, context
        messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-1",
                        "name": "read_file",
                        "input": {"path": "README.md"},
                    }
                ],
            }
        )
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-1",
                        "content": "README content",
                    }
                ],
            }
        )
        messages.append({"role": "assistant", "content": [{"type": "text", "text": "done"}]})

    adapter = AgentRuntimeAdapter(
        runtime_factory=lambda config_path: FakeRuntime(),
        loop_runner=fake_loop,
    )

    result = adapter.run_turn(
        conversation_id="conv-1",
        user_id="user-1",
        history=[],
        user_message={"role": "user", "content_text": "read README"},
        workspace_path=str(tmp_path),
    )

    assert result.tool_calls[0].external_id == "tool-1"
    assert result.tool_calls[0].tool_name == "read_file"
    assert result.tool_results[0].tool_call_external_id == "tool-1"
    assert result.tool_results[0].output_text == "README content"
    assert result.final_text == "done"
