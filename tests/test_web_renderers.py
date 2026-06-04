from __future__ import annotations

from types import SimpleNamespace

from web.renderers import export_display_messages, messages_to_display


def test_messages_to_display_handles_tool_blocks():
    messages = [
        {
            "role": "assistant",
            "content": [
                SimpleNamespace(type="text", text="I will inspect the workspace."),
                SimpleNamespace(
                    type="tool_use",
                    id="toolu_1",
                    name="bash",
                    input={"command": "pwd"},
                ),
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "D:\\workspace",
                }
            ],
        },
    ]

    display = messages_to_display(messages)

    assert display[0]["content"][0]["text"] == "I will inspect the workspace."
    assert display[0]["content"][1]["name"] == "bash"
    assert display[1]["role"] == "assistant"
    assert display[1]["content"][0]["content"] == "D:\\workspace"


def test_export_display_messages_returns_json_and_markdown():
    display = [{"role": "user", "raw_role": "user", "content": [{"type": "text", "text": "hello"}]}]

    json_data, markdown_data = export_display_messages(display)

    assert '"hello"' in json_data
    assert "# CodeAgent-Harness Chat" in markdown_data
    assert "hello" in markdown_data
