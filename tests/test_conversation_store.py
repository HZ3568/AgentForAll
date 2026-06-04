from __future__ import annotations

import json
from types import SimpleNamespace

from codeagent.sessions.store import ConversationStore, normalize_history
from web.renderers import messages_to_display


def test_conversation_store_create_list_load_save_delete(tmp_path):
    store = ConversationStore(tmp_path)

    created = store.create(title="Initial", history=[{"role": "user", "content": "hello"}])

    assert created["message_count"] == 1
    assert (tmp_path / ".sessions" / "index.json").exists()
    assert store.list()[0]["id"] == created["id"]

    loaded = store.load(created["id"])
    assert loaded["title"] == "Initial"
    assert loaded["history"][0]["content"] == "hello"

    saved = store.save(
        created["id"],
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    )
    assert saved["message_count"] == 2
    assert store.load(created["id"])["history"][1]["content"] == "hi"

    store.delete(created["id"])
    assert store.list() == []
    assert not (tmp_path / ".sessions" / f"{created['id']}.json").exists()


def test_conversation_store_save_can_create_session_with_inferred_title(tmp_path):
    store = ConversationStore(tmp_path)

    saved = store.save("manual_session", [{"role": "user", "content": "Build the web chat"}])

    assert saved["title"] == "Build the web chat"
    assert store.load("manual_session")["message_count"] == 1


def test_normalize_history_handles_text_tool_use_and_tool_result(tmp_path):
    tool_use = SimpleNamespace(
        type="tool_use",
        id="toolu_1",
        name="bash",
        input={"command": "pwd"},
    )
    history = [
        {"role": "user", "content": "inspect"},
        {
            "role": "assistant",
            "content": [
                SimpleNamespace(type="text", text="Running a command."),
                tool_use,
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

    normalized = normalize_history(history)

    assert normalized[1]["content"][0] == {"type": "text", "text": "Running a command."}
    assert normalized[1]["content"][1]["name"] == "bash"
    assert normalized[2]["content"][0]["type"] == "tool_result"
    json.dumps(normalized, ensure_ascii=False)


def test_loaded_session_history_can_render_display_messages(tmp_path):
    store = ConversationStore(tmp_path)
    session = store.create(
        history=[
            {"role": "user", "content": "list files"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "bash",
                        "input": {"command": "ls"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "README.md",
                    }
                ],
            },
        ]
    )

    loaded = store.load(session["id"])
    display = messages_to_display(loaded["history"])

    assert display[0]["role"] == "user"
    assert display[1]["content"][0]["name"] == "bash"
    assert display[2]["role"] == "assistant"
    assert display[2]["content"][0]["content"] == "README.md"
