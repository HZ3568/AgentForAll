from __future__ import annotations

import streamlit as st

from web.agent_session import (
    ACTIVE_SESSION_ID_KEY,
    delete_current_session,
    get_conversation_store,
    load_agent_session,
    rename_current_session,
    start_new_chat,
)


def _session_label(session: dict, active_id: str | None) -> str:
    marker = "● " if session.get("id") == active_id else ""
    title = session.get("title") or "New Chat"
    count = session.get("message_count", 0)
    return f"{marker}{title} ({count})"


def render_conversation_sidebar() -> None:
    store = get_conversation_store()
    active_id = st.session_state.get(ACTIVE_SESSION_ID_KEY)

    st.sidebar.title("Conversations")
    if st.sidebar.button("+ New Chat", use_container_width=True):
        start_new_chat()
        st.rerun()

    sessions = store.list()
    st.sidebar.subheader("Recent")
    if not sessions:
        st.sidebar.caption("No saved sessions yet.")
    for session in sessions:
        if st.sidebar.button(
            _session_label(session, active_id),
            key=f"load_session_{session['id']}",
            use_container_width=True,
        ):
            load_agent_session(session["id"])
            st.rerun()

    st.sidebar.divider()
    if active_id:
        current = store.load(active_id)
        with st.sidebar.expander("Rename current chat", expanded=False):
            title = st.text_input("Title", value=current.get("title", ""), key="rename_chat_title")
            if st.button("Rename", use_container_width=True):
                rename_current_session(title)
                st.rerun()

        if st.sidebar.button("Delete current chat", use_container_width=True):
            delete_current_session()
            st.rerun()
    else:
        st.sidebar.caption("Current chat is not saved yet.")
