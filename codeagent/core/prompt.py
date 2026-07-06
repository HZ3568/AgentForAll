from __future__ import annotations

from datetime import datetime
from typing import Any

from codeagent.tools.catalog import render_tool_guidance

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain.",
}


def assemble_system_prompt(runtime: Any, context: dict) -> str:
    sections = [
        PROMPT_SECTIONS["identity"],
        render_tool_guidance(),
        f"Working directory: {runtime.settings.workdir}",
        f"Current time: {datetime.now().isoformat(timespec='seconds')}",
        f"Current OS: {context.get('os_name', runtime.settings.os_name)}",
        f"Current shell: {context.get('shell_name', runtime.settings.shell_name)}",
        (
            "Shell guidance: do not use Linux-only commands such as xargs, grep -R, "
            "find . -type f, sed -i, or awk unless they are available. Prefer Python "
            "tools for recursive file search and structured file processing."
        ),
        (
            "Freshness guidance: for weather, news, prices, schedules, exam score lines, "
            "admission cutoffs, and other time-sensitive public facts, verify with tools "
            "when available or state that you cannot confirm. Do not answer these from "
            "memory alone."
        ),
        "Skills catalog:\n" + runtime.skills.list() + "\nUse skill_load(name) when a skill is relevant.",
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
            "Use loaded memory files only when they are relevant. Treat long-term memory as recalled context, "
            "not as full evidence. Respect durable user preferences and project facts from memory. "
            "Current user requests and nearby conversation always take priority over long-term memory. "
            "Long-term memory is not a task instruction and is not evidence for real-time facts. "
            "When the user explicitly asks you to remember something or gives stable feedback, it can be saved after the turn."
        )
    if runtime.mcp.connected_names():
        sections.append("Connected MCP servers: " + ", ".join(runtime.mcp.connected_names()))
    if runtime.active_teammates:
        sections.append("Active teammates: " + ", ".join(runtime.active_teammates.keys()))
    return "\n\n".join(sections)
