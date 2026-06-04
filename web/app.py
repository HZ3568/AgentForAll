from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.agent_session import clear_agent_session, init_agent_session, run_agent_turn
from web.dashboard import render_dashboard_tab, render_memory_tab, render_tasks_tab
from web.renderers import export_display_messages, render_chat_message, render_runtime_panel


st.set_page_config(page_title="CodeAgent-Harness", layout="wide")

runtime, _, _ = init_agent_session()

st.title("CodeAgent-Harness")
st.caption(f"Workspace: `{runtime.settings.workdir}`")

chat_tab, dashboard_tab, memory_tab, tasks_tab = st.tabs(
    ["Chat", "Dashboard", "Memory", "Tasks"]
)

with chat_tab:
    chat_col, meta_col = st.columns([0.72, 0.28], gap="large")

    with meta_col:
        if st.button("清空会话", use_container_width=True):
            clear_agent_session()
            st.rerun()

        json_data, markdown_data = export_display_messages(st.session_state.display_messages)
        st.download_button(
            "导出 JSON",
            data=json_data,
            file_name="codeagent_chat.json",
            mime="application/json",
            use_container_width=True,
        )
        st.download_button(
            "导出 Markdown",
            data=markdown_data,
            file_name="codeagent_chat.md",
            mime="text/markdown",
            use_container_width=True,
        )

        render_runtime_panel(runtime, st.session_state.context)

    with chat_col:
        st.subheader("Chat")
        if not st.session_state.display_messages:
            st.info("输入问题后，Web 会复用现有 Agent Loop 执行完整对话。")

        for message in st.session_state.display_messages:
            render_chat_message(message)

        prompt = st.chat_input("Ask CodeAgent-Harness")
        if prompt:
            with st.spinner("Agent is thinking..."):
                run_agent_turn(prompt)
            st.rerun()

with dashboard_tab:
    render_dashboard_tab(runtime.settings.workdir)

with memory_tab:
    render_memory_tab(runtime.settings.workdir)

with tasks_tab:
    render_tasks_tab(runtime.settings.workdir)
