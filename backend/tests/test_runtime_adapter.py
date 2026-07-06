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
    captured_messages = []

    def fake_loop(runtime: Any, messages: list[dict[str, Any]], context: dict[str, Any]) -> None:
        del runtime, context
        captured_messages.extend(messages)
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
    assert captured_messages[-1]["content"] == "hi"


def test_runtime_adapter_prefixes_user_message_when_web_search_is_enabled(tmp_path):
    captured_messages = []

    def fake_loop(runtime: Any, messages: list[dict[str, Any]], context: dict[str, Any]) -> None:
        del runtime, context
        captured_messages.extend(messages)
        messages.append({"role": "assistant", "content": [{"type": "text", "text": "searched"}]})

    adapter = AgentRuntimeAdapter(
        runtime_factory=lambda config_path: FakeRuntime(),
        loop_runner=fake_loop,
    )

    result = adapter.run_turn(
        conversation_id="conv-1",
        user_id="user-1",
        history=[],
        user_message={"role": "user", "content_json": {"type": "text", "text": "今年高考本科分数线"}},
        workspace_path=str(tmp_path),
        web_search_enabled=True,
    )

    assert result.error is None
    content = captured_messages[-1]["content"]
    assert "web_search" in content
    assert "必须先调用" in content
    assert "今年高考本科分数线" in content


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


def test_runtime_adapter_collects_assistant_after_history_compaction(tmp_path):
    def fake_loop(runtime: Any, messages: list[dict[str, Any]], context: dict[str, Any]) -> None:
        del runtime, context
        messages[:] = [{"role": "user", "content": "[Compacted]"}]
        messages.append({"role": "assistant", "content": [{"type": "text", "text": "after compact"}]})

    adapter = AgentRuntimeAdapter(
        runtime_factory=lambda config_path: FakeRuntime(),
        loop_runner=fake_loop,
    )

    result = adapter.run_turn(
        conversation_id="conv-1",
        user_id="user-1",
        history=[
            {"role": "user", "content_text": "one"},
            {"role": "assistant", "content_text": "two"},
            {"role": "user", "content_text": "three"},
        ],
        user_message={"role": "user", "content_text": "continue"},
        workspace_path=str(tmp_path),
    )

    assert result.error is None
    assert result.final_text == "after compact"
    assert result.assistant_messages[0]["content_text"] == "after compact"


def test_runtime_adapter_streaming_emits_callbacks(monkeypatch, tmp_path):
    def fake_streaming_loop(runtime: Any, messages: list[dict[str, Any]], context: dict[str, Any], callbacks) -> None:
        del runtime, context
        callbacks.on_text_delta("hello ")
        callbacks.on_text_delta("stream")
        block = {
            "type": "tool_use",
            "id": "tool-1",
            "name": "read_file",
            "input": {"path": "README.md"},
        }
        callbacks.on_tool_call_started(block)
        callbacks.on_tool_call_finished(block, "README content", "succeeded")
        messages.append({"role": "assistant", "content": [{"type": "text", "text": "hello stream"}]})

    monkeypatch.setattr("backend.app.runtime.agent_adapter.agent_loop_streaming", fake_streaming_loop)
    adapter = AgentRuntimeAdapter(runtime_factory=lambda config_path: FakeRuntime())
    events = []
    tool_calls = []
    tool_results = []

    result = adapter.run_turn_streaming(
        conversation_id="conv-1",
        user_id="user-1",
        history=[],
        user_message={"role": "user", "content_text": "hi"},
        workspace_path=str(tmp_path),
        on_event=events.append,
        on_tool_call=tool_calls.append,
        on_tool_result=tool_results.append,
    )

    assert result.final_text == "hello stream"
    assert events[0].event_type == "assistant_delta"
    assert events[0].event_json == {"role": "assistant", "delta": "hello stream"}
    assert [record.status for record in tool_calls] == ["running", "succeeded"]
    assert tool_results[0].tool_call_external_id == "tool-1"
    assert result.events == events


def test_runtime_adapter_streaming_collects_assistant_after_history_compaction(monkeypatch, tmp_path):
    def fake_streaming_loop(runtime: Any, messages: list[dict[str, Any]], context: dict[str, Any], callbacks) -> None:
        del runtime, context
        callbacks.on_text_delta("after ")
        messages[:] = [{"role": "user", "content": "[Compacted]"}]
        callbacks.on_text_delta("compact")
        messages.append({"role": "assistant", "content": [{"type": "text", "text": "after compact"}]})

    monkeypatch.setattr("backend.app.runtime.agent_adapter.agent_loop_streaming", fake_streaming_loop)
    adapter = AgentRuntimeAdapter(runtime_factory=lambda config_path: FakeRuntime())

    result = adapter.run_turn_streaming(
        conversation_id="conv-1",
        user_id="user-1",
        history=[
            {"role": "user", "content_text": "one"},
            {"role": "assistant", "content_text": "two"},
            {"role": "user", "content_text": "three"},
        ],
        user_message={"role": "user", "content_text": "continue"},
        workspace_path=str(tmp_path),
    )

    assert result.error is None
    assert result.final_text == "after compact"
    assert result.assistant_messages[0]["content_text"] == "after compact"


def test_runtime_adapter_streaming_uses_deltas_when_final_message_is_missing(monkeypatch, tmp_path):
    def fake_streaming_loop(runtime: Any, messages: list[dict[str, Any]], context: dict[str, Any], callbacks) -> None:
        del runtime, messages, context
        callbacks.on_text_delta("partial ")
        callbacks.on_text_delta("answer")

    monkeypatch.setattr("backend.app.runtime.agent_adapter.agent_loop_streaming", fake_streaming_loop)
    adapter = AgentRuntimeAdapter(runtime_factory=lambda config_path: FakeRuntime())

    result = adapter.run_turn_streaming(
        conversation_id="conv-1",
        user_id="user-1",
        history=[],
        user_message={"role": "user", "content_text": "hi"},
        workspace_path=str(tmp_path),
    )

    assert result.error is None
    assert result.final_text == "partial answer"
    assert result.assistant_messages == [
        {
            "role": "assistant",
            "content_json": {"type": "text", "text": "partial answer"},
            "content_text": "partial answer",
        }
    ]
