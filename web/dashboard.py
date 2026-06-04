from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _task_rows(workdir: Path) -> list[dict[str, Any]]:
    tasks_dir = workdir / ".tasks"
    if not tasks_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(tasks_dir.glob("task_*.json")):
        item = _read_json(path, {})
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _cron_rows(workdir: Path) -> list[dict[str, Any]]:
    data = _read_json(workdir / ".scheduled_tasks.json", [])
    return data if isinstance(data, list) else []


def _memory_files(workdir: Path) -> list[Path]:
    memory_dir = workdir / ".memory"
    if not memory_dir.exists():
        return []
    return sorted(path for path in memory_dir.glob("*.md") if path.name != "MEMORY.md")


def _worktree_dirs(workdir: Path) -> list[Path]:
    worktrees_dir = workdir / ".worktrees"
    if not worktrees_dir.exists():
        return []
    return sorted(path for path in worktrees_dir.iterdir() if path.is_dir())


def render_dashboard_tab(workdir: Path) -> None:
    tasks = _task_rows(workdir)
    crons = _cron_rows(workdir)
    memories = _memory_files(workdir)
    worktrees = _worktree_dirs(workdir)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tasks", len(tasks))
    col2.metric("Cron Jobs", len(crons))
    col3.metric("Memory", len(memories))
    col4.metric("Worktrees", len(worktrees))

    st.subheader("Scheduled Jobs")
    if crons:
        st.dataframe(crons, use_container_width=True)
    else:
        st.info("No durable cron file found.")

    st.subheader("Worktrees")
    if worktrees:
        st.dataframe(
            [{"name": path.name, "path": str(path)} for path in worktrees],
            use_container_width=True,
        )
    else:
        st.info("No worktrees found.")

    st.subheader("Recent Tasks")
    if tasks:
        st.dataframe(tasks[-10:], use_container_width=True)
    else:
        st.info("No tasks found. Run the CLI or Web chat and ask the agent to create tasks.")

    st.subheader("Memory Preview")
    memory_index = workdir / ".memory" / "MEMORY.md"
    if memory_index.exists():
        st.code(memory_index.read_text(encoding="utf-8")[:4000])
    else:
        st.info("No memory index found yet. The agent creates `.memory/MEMORY.md` after durable memories are extracted.")


def render_memory_tab(workdir: Path) -> None:
    memory_index = workdir / ".memory" / "MEMORY.md"
    memory_files = _memory_files(workdir)

    st.subheader("Memory Preview")
    if memory_index.exists():
        st.code(memory_index.read_text(encoding="utf-8")[:4000])
    else:
        st.info("No memory index found yet. The agent creates `.memory/MEMORY.md` after durable memories are extracted.")

    st.subheader("Memory Files")
    if memory_files:
        st.dataframe(
            [{"name": path.name, "size": path.stat().st_size, "path": str(path)} for path in memory_files],
            use_container_width=True,
        )
    else:
        st.info("No memory files found.")


def render_tasks_tab(workdir: Path) -> None:
    tasks = _task_rows(workdir)
    st.subheader("Tasks")
    if tasks:
        st.dataframe(tasks, use_container_width=True)
    else:
        st.info("No tasks found. Run the CLI or Web chat and ask the agent to create tasks.")
