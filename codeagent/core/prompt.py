from __future__ import annotations

from datetime import datetime
from typing import Any

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain.",
    "tools": (
        "Available tools: bash, read_file, write_file, edit_file, glob, web_search, "
        "fetch_url, pdf_extract, list_dir, find_files, search_text, read_spreadsheet, "
        "extract_pdf_text, extract_pdf_tables, transcribe_audio, ocr_image, todo_write, "
        "task, load_skill, compact, create_task, list_tasks, get_task, claim_task, "
        "complete_task, schedule_cron, list_crons, cancel_cron, spawn_teammate, "
        "send_message, check_inbox, request_shutdown, request_plan, review_plan, "
        "create_worktree, remove_worktree, keep_worktree, connect_mcp. MCP tools are "
        "prefixed mcp__{server}__{tool}."
    ),
}


def assemble_system_prompt(runtime: Any, context: dict) -> str:
    sections = [
        PROMPT_SECTIONS["identity"],
        PROMPT_SECTIONS["tools"],
        f"Working directory: {runtime.settings.workdir}",
        f"Current time: {datetime.now().isoformat(timespec='seconds')}",
        f"Current OS: {context.get('os_name', runtime.settings.os_name)}",
        f"Current shell: {context.get('shell_name', runtime.settings.shell_name)}",
        (
            "Shell guidance: do not use Linux-only commands such as xargs, grep -R, "
            "find . -type f, sed -i, or awk unless they are available. Prefer Python "
            "tools for recursive file search and structured file processing."
        ),
        "Skills catalog:\n" + runtime.skills.list() + "\nUse load_skill(name) when a skill is relevant.",
    ]
    if context.get("mode") == "gaia_eval":
        sections.append(
            "You are in GAIA evaluation mode.\n"
            "Do not answer from vague memory.\n"
            "Every final answer must be grounded in observed tool output.\n"
            "Todo state is not evidence.\n"
            "If required evidence is unavailable after trying relevant tools, return UNRESOLVED instead of guessing.\n"
            "Keep the final answer concise and match the requested answer format exactly.\n"
            f"Sample scratch directory: {context.get('scratch_dir') or '(not set)'}\n"
            "Write all temporary files into the sample scratch directory."
        )
    if context.get("memories"):
        sections.append(
            "Memory context:\n"
            f"{context['memories']}\n\n"
            "Use loaded memory files when they are relevant. Treat the memory index as a catalog, "
            "not as full evidence. Respect durable user preferences and project facts from memory. "
            "When the user explicitly asks you to remember something or gives stable feedback, it can be saved after the turn."
        )
    if runtime.mcp.connected_names():
        sections.append("Connected MCP servers: " + ", ".join(runtime.mcp.connected_names()))
    if runtime.active_teammates:
        sections.append("Active teammates: " + ", ".join(runtime.active_teammates.keys()))
    return "\n\n".join(sections)
