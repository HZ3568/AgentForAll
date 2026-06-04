from __future__ import annotations

from typing import Any

import streamlit as st

from codeagent.core.loop import agent_loop
from codeagent.core.runtime import create_runtime
from web.renderers import messages_to_display


RUNTIME_KEY = "runtime"
HISTORY_KEY = "history"
CONTEXT_KEY = "context"
DISPLAY_MESSAGES_KEY = "display_messages"


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

    return (
        runtime,
        st.session_state[HISTORY_KEY],
        st.session_state[CONTEXT_KEY],
    )


def clear_agent_session() -> None:
    runtime, _, _ = init_agent_session()
    st.session_state[HISTORY_KEY] = []
    st.session_state[CONTEXT_KEY] = runtime.update_context({}, [])
    st.session_state[DISPLAY_MESSAGES_KEY] = []


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
    return new_display_messages
