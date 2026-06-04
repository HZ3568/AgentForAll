from __future__ import annotations

from codeagent.core.cli import CliSessionController, format_sessions
from codeagent.sessions.store import ConversationStore


class DummyRuntime:
    def update_context(self, context: dict, messages: list) -> dict:
        return {
            "message_count": len(messages),
            "history_id": id(messages),
            "previous_context_keys": sorted(context.keys()),
        }


def make_controller(tmp_path, history: list | None = None, context: dict | None = None):
    runtime = DummyRuntime()
    store = ConversationStore(tmp_path)
    current_history = history if history is not None else []
    current_context = context if context is not None else {}
    return CliSessionController(runtime, store, current_history, current_context)


def test_cli_save_creates_then_updates_active_session(tmp_path):
    history = [{"role": "user", "content": "hello"}]
    controller = make_controller(tmp_path, history)

    created = controller.save_current_session()
    active_id = created["id"]
    history.append({"role": "assistant", "content": "hi"})
    saved = controller.save_current_session()

    assert saved["id"] == active_id
    assert controller.store.load(active_id)["message_count"] == 2
    assert len(controller.store.list()) == 1


def test_cli_load_replaces_history_and_context_in_place(tmp_path):
    history = [{"role": "user", "content": "old"}]
    context = {"stale": True}
    controller = make_controller(tmp_path, history, context)
    session = controller.store.create(history=[{"role": "user", "content": "loaded"}])

    history_id = id(history)
    context_id = id(context)
    loaded = controller.load_session(session["id"])

    assert id(history) == history_id
    assert id(context) == context_id
    assert history == loaded["history"]
    assert context["message_count"] == 1
    assert context["history_id"] == history_id
    assert "stale" not in context
    assert controller.active_session_id == session["id"]


def test_cli_new_saves_current_then_clears_in_place(tmp_path):
    history = [{"role": "user", "content": "keep this"}]
    context = {"stale": True}
    controller = make_controller(tmp_path, history, context)

    history_id = id(history)
    context_id = id(context)
    saved = controller.start_new_session()

    assert id(history) == history_id
    assert id(context) == context_id
    assert history == []
    assert context["message_count"] == 0
    assert controller.active_session_id is None
    assert controller.store.load(saved["id"])["history"][0]["content"] == "keep this"


def test_format_sessions_marks_active_session(tmp_path):
    controller = make_controller(tmp_path)
    session = controller.store.create(title="Current", history=[])

    output = format_sessions(controller.store.list(), session["id"])

    assert f"* {session['id']}" in output
    assert "Current" in output
