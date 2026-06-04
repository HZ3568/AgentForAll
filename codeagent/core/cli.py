from __future__ import annotations

import threading
from typing import Any

from codeagent.core.loop import agent_loop, cron_autorun_loop, print_turn_assistants
from codeagent.sessions.store import ConversationStore


HELP_TEXT = """Commands:
  /help                 Show this help.
  /new                  Save the current session and start a new empty session.
  /sessions             List saved sessions.
  /load <session_id>    Load a saved session.
  /rename <title>       Rename the current session.
  /delete               Delete the current session.
  /delete <session_id>  Delete a saved session.
  /save                 Save the current session.
  q, exit               Quit.
"""


class CliSessionController:
    def __init__(self, runtime: Any, store: ConversationStore, history: list, context: dict) -> None:
        self.runtime = runtime
        self.store = store
        self.history = history
        self.context = context
        self.active_session_id: str | None = None

    def refresh_context(self) -> None:
        self.context.clear()
        self.context.update(self.runtime.update_context({}, self.history))

    def save_current_session(self) -> dict[str, Any]:
        if self.active_session_id:
            return self.store.save(self.active_session_id, self.history)

        session = self.store.create(history=self.history)
        self.active_session_id = session["id"]
        return session

    def start_new_session(self) -> dict[str, Any]:
        saved = self.save_current_session()
        self.history[:] = []
        self.active_session_id = None
        self.refresh_context()
        return saved

    def load_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.load(session_id)
        self.history[:] = session["history"]
        self.active_session_id = session["id"]
        self.refresh_context()
        return session

    def rename_current_session(self, title: str) -> dict[str, Any]:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Title cannot be empty.")
        if not self.active_session_id:
            self.save_current_session()
        return self.store.save(self.active_session_id, self.history, title=clean_title)

    def delete_session(self, session_id: str | None = None) -> str | None:
        target_id = session_id or self.active_session_id
        if target_id:
            self.store.delete(target_id)
        if session_id is None or target_id == self.active_session_id:
            self.history[:] = []
            self.active_session_id = None
            self.refresh_context()
        return target_id


def format_sessions(sessions: list[dict[str, Any]], active_session_id: str | None = None) -> str:
    if not sessions:
        return "No saved sessions."

    lines = ["Saved sessions:"]
    for session in sessions:
        marker = "*" if session.get("id") == active_session_id else " "
        title = session.get("title") or "New Chat"
        updated_at = session.get("updated_at") or "-"
        count = session.get("message_count", 0)
        lines.append(f"{marker} {session.get('id')} | {updated_at} | {count} messages | {title}")
    return "\n".join(lines)


def handle_cli_command(query: str, controller: CliSessionController) -> None:
    command, _, argument = query.strip().partition(" ")
    argument = argument.strip()

    try:
        if command == "/help":
            print(HELP_TEXT.rstrip())
            return
        if command == "/new":
            saved = controller.start_new_session()
            print(f"Saved session {saved['id']}. Started a new session.")
            return
        if command == "/sessions":
            print(format_sessions(controller.store.list(), controller.active_session_id))
            return
        if command == "/load":
            if not argument:
                print("Usage: /load <session_id>")
                return
            session = controller.load_session(argument)
            print(f"Loaded session {session['id']}: {session.get('title', 'New Chat')} ({session['message_count']} messages).")
            return
        if command == "/rename":
            if not argument:
                print("Usage: /rename <title>")
                return
            session = controller.rename_current_session(argument)
            print(f"Renamed session {session['id']}: {session.get('title', 'New Chat')}")
            return
        if command == "/delete":
            deleted_id = controller.delete_session(argument or None)
            if deleted_id:
                print(f"Deleted session {deleted_id}.")
            else:
                print("Discarded current unsaved session.")
            return
        if command == "/save":
            session = controller.save_current_session()
            print(f"Saved session {session['id']} ({session['message_count']} messages).")
            return
    except Exception as exc:
        print(f"Command failed: {type(exc).__name__}: {exc}")
        return

    print(f"Unknown command: {command}. Type /help for commands.")


def append_lead_inbox(runtime: Any, history: list) -> None:
    inbox = runtime.protocols.consume_lead_inbox(route_protocol=True)
    if not inbox:
        return

    def label(msg: dict) -> str:
        req_id = msg.get("metadata", {}).get("request_id", "")
        suffix = f" req:{req_id}" if req_id else ""
        return f"{msg.get('type', 'message')}{suffix}"

    inbox_text = "\n".join(
        f"From {msg['from']} [{label(msg)}]: {msg['content'][:200]}" for msg in inbox
    )
    history.append({"role": "user", "content": f"[Inbox]\n{inbox_text}"})


def main() -> None:
    from codeagent.core.runtime import create_runtime

    runtime = create_runtime()
    runtime.cli_active = True
    store = ConversationStore(runtime.settings.workdir)
    print("CodeAgent-Harness")
    print("Enter a question, press Enter to send. Type /help for commands. Type q to quit.\n")
    history: list = []
    context = runtime.update_context({}, history)
    controller = CliSessionController(runtime, store, history, context)
    threading.Thread(
        target=cron_autorun_loop,
        args=(runtime, history, context, controller.save_current_session),
        daemon=True,
    ).start()
    while True:
        try:
            query = input(runtime.settings.prompt)
        except (EOFError, KeyboardInterrupt):
            break
        stripped = query.strip()
        if stripped.lower() in ("q", "exit", ""):
            break
        if stripped.startswith("/"):
            with runtime.agent_lock:
                handle_cli_command(stripped, controller)
            print()
            continue

        runtime.hooks.trigger("UserPromptSubmit", query)
        with runtime.agent_lock:
            turn_start = len(history)
            history.append({"role": "user", "content": query})
            agent_loop(runtime, history, context)
            controller.refresh_context()
            print_turn_assistants(runtime, history, turn_start)
            append_lead_inbox(runtime, history)
            controller.save_current_session()
        print()


if __name__ == "__main__":
    main()
