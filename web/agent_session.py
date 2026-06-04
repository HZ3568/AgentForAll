from __future__ import annotations

from typing import Any

import streamlit as st

from codeagent.core.loop import agent_loop
from codeagent.core.runtime import create_runtime
from codeagent.sessions.store import ConversationStore
from web.renderers import messages_to_display


RUNTIME_KEY = "runtime"
HISTORY_KEY = "history"
CONTEXT_KEY = "context"
DISPLAY_MESSAGES_KEY = "display_messages"
CONVERSATION_STORE_KEY = "conversation_store"
ACTIVE_SESSION_ID_KEY = "active_session_id"


def init_agent_session() -> tuple[Any, list, dict]:
    """Initialize per-browser-tab agent state in Streamlit session_state.

    Streamlit reruns the script on every interaction, so runtime/history/context
    must live in session_state to preserve the Agent Loop state across turns.
    """

    if RUNTIME_KEY not in st.session_state:
        runtime = create_runtime()
        runtime.cli_active = False
        st.session_state[RUNTIME_KEY] = runtime

    runtime = st.session_state[RUNTIME_KEY]

    if HISTORY_KEY not in st.session_state:
        st.session_state[HISTORY_KEY] = []

    if CONTEXT_KEY not in st.session_state:
        st.session_state[CONTEXT_KEY] = runtime.update_context({}, [])

    if DISPLAY_MESSAGES_KEY not in st.session_state:
        st.session_state[DISPLAY_MESSAGES_KEY] = []

    if CONVERSATION_STORE_KEY not in st.session_state:
        st.session_state[CONVERSATION_STORE_KEY] = ConversationStore(runtime.settings.workdir)

    if ACTIVE_SESSION_ID_KEY not in st.session_state:
        st.session_state[ACTIVE_SESSION_ID_KEY] = None

    return (
        runtime,
        st.session_state[HISTORY_KEY],
        st.session_state[CONTEXT_KEY],
    )


def get_conversation_store() -> ConversationStore:
    runtime, _, _ = init_agent_session()
    if CONVERSATION_STORE_KEY not in st.session_state:
        st.session_state[CONVERSATION_STORE_KEY] = ConversationStore(runtime.settings.workdir)
    return st.session_state[CONVERSATION_STORE_KEY]


def start_new_chat() -> None:
    runtime, _, _ = init_agent_session()
    st.session_state[HISTORY_KEY] = []
    st.session_state[CONTEXT_KEY] = runtime.update_context({}, [])
    st.session_state[DISPLAY_MESSAGES_KEY] = []
    st.session_state[ACTIVE_SESSION_ID_KEY] = None


def clear_agent_session() -> None:
    start_new_chat()


def load_agent_session(session_id: str) -> None:
    runtime, _, _ = init_agent_session()
    session = get_conversation_store().load(session_id)
    history = session["history"]
    st.session_state[HISTORY_KEY] = history
    st.session_state[CONTEXT_KEY] = runtime.update_context({}, history)
    st.session_state[DISPLAY_MESSAGES_KEY] = messages_to_display(history)
    st.session_state[ACTIVE_SESSION_ID_KEY] = session_id


def save_active_session() -> dict[str, Any]:
    _, history, _ = init_agent_session()
    store = get_conversation_store()
    active_id = st.session_state.get(ACTIVE_SESSION_ID_KEY)
    if active_id:
        session = store.save(active_id, history)
    else:
        session = store.create(history=history)
        st.session_state[ACTIVE_SESSION_ID_KEY] = session["id"]
    return session


def rename_current_session(title: str) -> None:
    active_id = st.session_state.get(ACTIVE_SESSION_ID_KEY)
    if active_id:
        get_conversation_store().rename(active_id, title)


def delete_current_session() -> None:
    active_id = st.session_state.get(ACTIVE_SESSION_ID_KEY)
    if active_id:
        get_conversation_store().delete(active_id)
    start_new_chat()


def run_agent_turn(user_prompt: str) -> list[dict[str, Any]]:
    runtime, history, context = init_agent_session()

    runtime.hooks.trigger("UserPromptSubmit", user_prompt)

    user_message = {"role": "user", "content": user_prompt}
    history.append(user_message)
    st.session_state[DISPLAY_MESSAGES_KEY].extend(messages_to_display([user_message]))

    turn_content_start = len(history)
    with runtime.agent_lock:
        agent_loop(runtime, history, context)
        st.session_state[CONTEXT_KEY] = runtime.update_context(context, history)

    new_display_messages = messages_to_display(history[turn_content_start:])
    st.session_state[DISPLAY_MESSAGES_KEY].extend(new_display_messages)
    st.session_state[HISTORY_KEY] = history
    save_active_session()
    return new_display_messages
