from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from codeagent.agents.subagent import spawn_subagent
from codeagent.agents.teammate import spawn_teammate_thread
from codeagent.mcp.client import normalize_mcp_name
from codeagent.tools.agentic.todo import run_todo_write
from codeagent.tools.catalog import LEGACY_TOOL_ALIASES, TOOL_CATALOG
from codeagent.tools.documents.readers import (
    extract_pdf_tables,
    ocr_image,
    read_spreadsheet,
    transcribe_audio,
)
from codeagent.tools.network.fetch import run_fetch_url, run_pdf_extract
from codeagent.tools.network.search import run_web_search
from codeagent.tools.workspace.filesystem import (
    find_files,
    list_dir,
    run_bash,
    run_edit,
    run_glob,
    run_read,
    run_write,
    search_text,
)

BUILTIN_TOOLS: list[dict[str, Any]] = [tool.to_provider_tool() for tool in TOOL_CATALOG]


def build_builtin_handlers(runtime: Any) -> dict[str, Callable[..., str]]:
    cwd = runtime.settings.workdir
    handlers: dict[str, Callable[..., str]] = {
        "shell_run": lambda command, run_in_background=False: run_bash(
            command, cwd, run_in_background
        ),
        "file_read": lambda path, limit=None, offset=0: run_read(
            path, cwd, limit, offset
        ),
        "file_write": lambda path, content: _write_file(runtime, path, content),
        "file_edit": lambda path, old_text, new_text: run_edit(
            path, old_text, new_text, cwd
        ),
        "file_glob": lambda pattern: run_glob(pattern, cwd),
        "dir_list": lambda path=".", limit=200: list_dir(path, cwd, limit),
        "file_find": lambda root=".", pattern="*", limit=500: find_files(
            root, pattern, cwd, limit
        ),
        "text_search": lambda root=".", query="", include_globs=None, limit=100: search_text(
            root, query, cwd, include_globs, limit
        ),
        "web_search": lambda query, max_results=None, timeout=None: run_web_search(
            query, runtime.settings.web_search, max_results, timeout
        ),
        "web_fetch": lambda url, max_chars=20000, timeout=20: run_fetch_url(
            url, max_chars, timeout
        ),
        "pdf_extract_text": lambda source, max_pages=20, max_chars=50000, timeout=20: run_pdf_extract(
            source, cwd, max_pages, max_chars, timeout
        ),
        "pdf_extract_tables": lambda path, max_pages=20, max_chars=50000: extract_pdf_tables(
            path, cwd, max_pages, max_chars
        ),
        "spreadsheet_read": lambda path, sheet_name=None, max_rows=20: read_spreadsheet(
            path, cwd, sheet_name, max_rows
        ),
        "audio_transcribe": lambda path: transcribe_audio(path, cwd),
        "image_ocr": lambda path: ocr_image(path, cwd),
        "todo_set": lambda todos: run_todo_write(runtime, todos),
        "skill_load": lambda name: runtime.skills.load(name),
        "context_compact": lambda focus="": f"Context compaction requested: {focus}",
        "subagent_run": lambda description: spawn_subagent(runtime, description),
        "task_create": lambda subject, description="", blockedBy=None: _create_task(
            runtime, subject, description, blockedBy
        ),
        "task_list": lambda: runtime.tasks.render_list(),
        "task_get": lambda task_id: _get_task(runtime, task_id),
        "task_claim": lambda task_id: _claim_task(runtime, task_id),
        "task_complete": lambda task_id: _complete_task(runtime, task_id),
        "cron_schedule": lambda cron, prompt, recurring=True, durable=True: runtime.cron.schedule(
            cron, prompt, recurring, durable
        ),
        "cron_list": lambda: runtime.cron.list_jobs(),
        "cron_cancel": lambda job_id: runtime.cron.cancel(job_id),
        "teammate_spawn": lambda name, role, prompt: spawn_teammate_thread(
            runtime, name, role, prompt
        ),
        "teammate_send": lambda to, content: (
            runtime.bus.send("lead", to, content),
            f"Sent to {to}",
        )[1],
        "teammate_inbox": lambda: _check_inbox(runtime),
        "teammate_shutdown": lambda teammate: runtime.protocols.request_shutdown(
            teammate
        ),
        "teammate_request_plan": lambda teammate, task: runtime.protocols.request_plan(
            teammate, task
        ),
        "teammate_review_plan": lambda request_id, approve, feedback="": runtime.protocols.review_plan(
            request_id, approve, feedback
        ),
        "worktree_create": lambda name, task_id="": runtime.worktrees.create(
            name, task_id
        ),
        "worktree_remove": lambda name, discard_changes=False: runtime.worktrees.remove(
            name, discard_changes
        ),
        "worktree_keep": lambda name: runtime.worktrees.keep(name),
        "mcp_connect": lambda name: runtime.mcp.connect(name),
    }

    handlers.update(_legacy_handlers(handlers, cwd))
    return handlers


def _legacy_handlers(
    canonical_handlers: dict[str, Callable[..., str]],
    cwd: Path,
) -> dict[str, Callable[..., str]]:
    legacy = {
        old_name: canonical_handlers[new_name]
        for old_name, new_name in LEGACY_TOOL_ALIASES.items()
        if old_name not in {"extract_pdf_text", "extract_pdf_tables", "read_spreadsheet"}
    }
    legacy["extract_pdf_text"] = lambda path, max_pages=20, max_chars=50000: run_pdf_extract(
        path, cwd, max_pages=max_pages, max_chars=max_chars
    )
    legacy["extract_pdf_tables"] = canonical_handlers["pdf_extract_tables"]
    legacy["read_spreadsheet"] = canonical_handlers["spreadsheet_read"]
    return legacy


def _write_file(runtime: Any, path: str, content: str) -> str:
    if getattr(runtime, "mode", "default") == "gaia_eval" and not getattr(
        runtime, "allow_project_writes", True
    ):
        scratch = getattr(runtime, "current_scratch_dir", None)
        if not scratch:
            return "Error: GAIA scratch directory is not configured."
        scratch_dir = Path(scratch).resolve()
        requested = Path(path)
        if requested.is_absolute():
            try:
                requested.resolve().relative_to(scratch_dir)
            except ValueError:
                return (
                    "Error: GAIA mode blocks writing outside the sample scratch directory. "
                    f"Use scratch path: {scratch_dir}"
                )
            return run_write(str(requested.relative_to(scratch_dir)), content, scratch_dir)
        return run_write(path, content, scratch_dir)
    return run_write(path, content, runtime.settings.workdir)


def _create_task(
    runtime: Any,
    subject: str,
    description: str = "",
    blockedBy: list[str] | None = None,
) -> str:
    task = runtime.tasks.create(subject, description, blockedBy)
    deps = f" (blockedBy: {', '.join(blockedBy)})" if blockedBy else ""
    return f"Created {task.id}: {task.subject}{deps}"


def _get_task(runtime: Any, task_id: str) -> str:
    try:
        return runtime.tasks.to_json(task_id)
    except FileNotFoundError:
        return f"Error: task {task_id} not found"


def _claim_task(runtime: Any, task_id: str) -> str:
    try:
        return runtime.tasks.claim(task_id, owner="agent")
    except FileNotFoundError:
        return f"Error: task {task_id} not found"


def _complete_task(runtime: Any, task_id: str) -> str:
    try:
        return runtime.tasks.complete(task_id)
    except FileNotFoundError:
        return f"Error: task {task_id} not found"


def _check_inbox(runtime: Any) -> str:
    msgs = runtime.protocols.consume_lead_inbox(route_protocol=True)
    if not msgs:
        return "(inbox empty)"
    lines = []
    for msg in msgs:
        meta = msg.get("metadata", {})
        req_id = meta.get("request_id", "")
        tag = f" [{msg['type']} req:{req_id}]" if req_id else f" [{msg['type']}]"
        lines.append(f"  [{msg['from']}]{tag} {msg['content'][:200]}")
    return "\n".join(lines)


def build_tool_pool(
    runtime: Any,
) -> tuple[list[dict[str, Any]], dict[str, Callable[..., str]]]:
    tools = list(BUILTIN_TOOLS)
    handlers = build_builtin_handlers(runtime)
    for server_name, client in runtime.mcp.clients.items():
        safe_server = normalize_mcp_name(server_name)
        for tool_def in client.tools:
            safe_tool = normalize_mcp_name(tool_def["name"])
            prefixed = f"mcp__{safe_server}__{safe_tool}"
            tools.append(
                {
                    "name": prefixed,
                    "description": tool_def.get("description", ""),
                    "input_schema": tool_def.get("inputSchema", {}),
                }
            )
            handlers[prefixed] = lambda c=client, t=tool_def["name"], **kw: c.call_tool(
                t, kw
            )
    return tools, handlers
