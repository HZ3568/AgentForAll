from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    category: str
    description: str
    input_schema: dict[str, Any]

    def to_provider_tool(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": f"[{self.category}] {self.description}",
            "input_schema": self.input_schema,
        }


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


TOOL_CATALOG: list[ToolSpec] = [
    ToolSpec(
        "shell_run",
        "workspace",
        "Run a shell command in the workspace. Use for commands, tests, builds, and CLI tools.",
        _schema({"command": {"type": "string"}, "run_in_background": {"type": "boolean"}}, ["command"]),
    ),
    ToolSpec(
        "file_read",
        "workspace",
        "Read a text file. For binary or structured files, use the matching document tool.",
        _schema({"path": {"type": "string"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}}, ["path"]),
    ),
    ToolSpec(
        "file_write",
        "workspace",
        "Write UTF-8 text content to a workspace file.",
        _schema({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    ),
    ToolSpec(
        "file_edit",
        "workspace",
        "Replace exact text in a workspace file once.",
        _schema({"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, ["path", "old_text", "new_text"]),
    ),
    ToolSpec(
        "file_glob",
        "workspace",
        "Find files matching a non-recursive glob pattern. Prefer file_find for recursive searches.",
        _schema({"pattern": {"type": "string"}}, ["pattern"]),
    ),
    ToolSpec(
        "dir_list",
        "workspace",
        "List files and directories safely on Windows and Unix-like systems.",
        _schema({"path": {"type": "string"}, "limit": {"type": "integer"}}, ["path"]),
    ),
    ToolSpec(
        "file_find",
        "workspace",
        "Recursively find files by glob pattern using Python. Prefer this over shell find/xargs.",
        _schema({"root": {"type": "string"}, "pattern": {"type": "string"}, "limit": {"type": "integer"}}, ["root", "pattern"]),
    ),
    ToolSpec(
        "text_search",
        "workspace",
        "Search text files recursively using Python. Prefer this over grep/find/xargs.",
        _schema({"root": {"type": "string"}, "query": {"type": "string"}, "include_globs": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer"}}, ["root", "query"]),
    ),
    ToolSpec(
        "web_search",
        "web",
        "Search the public web through the configured provider and return structured result links.",
        _schema({"query": {"type": "string"}, "max_results": {"type": "integer"}, "timeout": {"type": "integer"}}, ["query"]),
    ),
    ToolSpec(
        "web_fetch",
        "web",
        "Fetch a URL and extract readable text from HTML or plain text pages.",
        _schema({"url": {"type": "string"}, "max_chars": {"type": "integer"}, "timeout": {"type": "integer"}}, ["url"]),
    ),
    ToolSpec(
        "pdf_extract_text",
        "documents",
        "Extract text from a PDF in the workspace or from a PDF URL.",
        _schema({"source": {"type": "string"}, "max_pages": {"type": "integer"}, "max_chars": {"type": "integer"}, "timeout": {"type": "integer"}}, ["source"]),
    ),
    ToolSpec(
        "pdf_extract_tables",
        "documents",
        "Extract tables from a workspace PDF using pdfplumber.",
        _schema({"path": {"type": "string"}, "max_pages": {"type": "integer"}, "max_chars": {"type": "integer"}}, ["path"]),
    ),
    ToolSpec(
        "spreadsheet_read",
        "documents",
        "Read CSV/XLS/XLSX files and return sheets, dimensions, columns, and preview rows.",
        _schema({"path": {"type": "string"}, "sheet_name": {"type": "string"}, "max_rows": {"type": "integer"}}, ["path"]),
    ),
    ToolSpec(
        "audio_transcribe",
        "documents",
        "Transcribe an audio file using the optional faster-whisper dependency.",
        _schema({"path": {"type": "string"}}, ["path"]),
    ),
    ToolSpec(
        "image_ocr",
        "documents",
        "Run OCR on an image using optional pytesseract dependency.",
        _schema({"path": {"type": "string"}}, ["path"]),
    ),
    ToolSpec(
        "todo_set",
        "agent_state",
        "Create or replace the task list for the current session.",
        _schema({"todos": {"type": "array", "items": {"type": "object", "properties": {"content": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["content", "status"]}}}, ["todos"]),
    ),
    ToolSpec("skill_load", "agent_state", "Load the full content of a skill by name.", _schema({"name": {"type": "string"}}, ["name"])),
    ToolSpec("context_compact", "agent_state", "Summarize earlier conversation and continue with compacted context.", _schema({"focus": {"type": "string"}})),
    ToolSpec("subagent_run", "tasking", "Launch a focused subagent. Returns only its final summary.", _schema({"description": {"type": "string"}}, ["description"])),
    ToolSpec("task_create", "tasking", "Create a task.", _schema({"subject": {"type": "string"}, "description": {"type": "string"}, "blockedBy": {"type": "array", "items": {"type": "string"}}}, ["subject"])),
    ToolSpec("task_list", "tasking", "List all tasks.", _schema({})),
    ToolSpec("task_get", "tasking", "Get full task details.", _schema({"task_id": {"type": "string"}}, ["task_id"])),
    ToolSpec("task_claim", "tasking", "Claim a pending task.", _schema({"task_id": {"type": "string"}}, ["task_id"])),
    ToolSpec("task_complete", "tasking", "Complete an in-progress task.", _schema({"task_id": {"type": "string"}}, ["task_id"])),
    ToolSpec("cron_schedule", "automation", "Schedule a cron job. cron is 5-field: min hour dom month dow.", _schema({"cron": {"type": "string"}, "prompt": {"type": "string"}, "recurring": {"type": "boolean"}, "durable": {"type": "boolean"}}, ["cron", "prompt"])),
    ToolSpec("cron_list", "automation", "List registered cron jobs.", _schema({})),
    ToolSpec("cron_cancel", "automation", "Cancel a cron job by ID.", _schema({"job_id": {"type": "string"}}, ["job_id"])),
    ToolSpec("teammate_spawn", "collaboration", "Spawn an autonomous teammate.", _schema({"name": {"type": "string"}, "role": {"type": "string"}, "prompt": {"type": "string"}}, ["name", "role", "prompt"])),
    ToolSpec("teammate_send", "collaboration", "Send a message to a teammate.", _schema({"to": {"type": "string"}, "content": {"type": "string"}}, ["to", "content"])),
    ToolSpec("teammate_inbox", "collaboration", "Check inbox for teammate messages and protocol responses.", _schema({})),
    ToolSpec("teammate_shutdown", "collaboration", "Request a teammate to shut down.", _schema({"teammate": {"type": "string"}}, ["teammate"])),
    ToolSpec("teammate_request_plan", "collaboration", "Ask a teammate to submit a plan.", _schema({"teammate": {"type": "string"}, "task": {"type": "string"}}, ["teammate", "task"])),
    ToolSpec("teammate_review_plan", "collaboration", "Approve or reject a submitted teammate plan.", _schema({"request_id": {"type": "string"}, "approve": {"type": "boolean"}, "feedback": {"type": "string"}}, ["request_id", "approve"])),
    ToolSpec("worktree_create", "workspace_isolation", "Create an isolated git worktree.", _schema({"name": {"type": "string"}, "task_id": {"type": "string"}}, ["name"])),
    ToolSpec("worktree_remove", "workspace_isolation", "Remove a worktree. Refuses if changes exist.", _schema({"name": {"type": "string"}, "discard_changes": {"type": "boolean"}}, ["name"])),
    ToolSpec("worktree_keep", "workspace_isolation", "Keep a worktree for manual review.", _schema({"name": {"type": "string"}}, ["name"])),
    ToolSpec("mcp_connect", "extensions", "Connect to an MCP server and discover its tools.", _schema({"name": {"type": "string"}}, ["name"])),
]

LEGACY_TOOL_ALIASES: dict[str, str] = {
    "bash": "shell_run",
    "read_file": "file_read",
    "write_file": "file_write",
    "edit_file": "file_edit",
    "glob": "file_glob",
    "list_dir": "dir_list",
    "find_files": "file_find",
    "search_text": "text_search",
    "fetch_url": "web_fetch",
    "pdf_extract": "pdf_extract_text",
    "extract_pdf_text": "pdf_extract_text",
    "extract_pdf_tables": "pdf_extract_tables",
    "read_spreadsheet": "spreadsheet_read",
    "transcribe_audio": "audio_transcribe",
    "ocr_image": "image_ocr",
    "todo_write": "todo_set",
    "load_skill": "skill_load",
    "compact": "context_compact",
    "task": "subagent_run",
    "create_task": "task_create",
    "list_tasks": "task_list",
    "get_task": "task_get",
    "claim_task": "task_claim",
    "complete_task": "task_complete",
    "schedule_cron": "cron_schedule",
    "list_crons": "cron_list",
    "cancel_cron": "cron_cancel",
    "spawn_teammate": "teammate_spawn",
    "send_message": "teammate_send",
    "check_inbox": "teammate_inbox",
    "request_shutdown": "teammate_shutdown",
    "request_plan": "teammate_request_plan",
    "review_plan": "teammate_review_plan",
    "create_worktree": "worktree_create",
    "remove_worktree": "worktree_remove",
    "keep_worktree": "worktree_keep",
    "connect_mcp": "mcp_connect",
}

CATEGORY_ORDER = [
    "workspace",
    "web",
    "documents",
    "agent_state",
    "tasking",
    "automation",
    "collaboration",
    "workspace_isolation",
    "extensions",
]

TOOL_SELECTION_RULES = [
    "实时公共信息先使用 web_search，再按需用 web_fetch 打开权威来源；搜索失败时说明失败原因和无法确认的范围。",
    "代码库检索优先使用 file_find/text_search/file_read；递归搜索不要优先用 shell_run 拼 find/grep/xargs。",
    "PDF 按需求选择 pdf_extract_text 或 pdf_extract_tables；网页 PDF 也使用 pdf_extract_text。",
    "写文件前先用 file_read 确认当前内容，再用 file_edit 精确替换或 file_write 写入 UTF-8 文本。",
    "长任务或多步工作用 todo_set 跟踪；只有需要隔离并行工作时才使用 subagent_run 或 teammate_*。",
]


def canonical_tool_name(name: str) -> str:
    return LEGACY_TOOL_ALIASES.get(name, name)


def render_tool_guidance() -> str:
    grouped: dict[str, list[ToolSpec]] = {category: [] for category in CATEGORY_ORDER}
    for tool in TOOL_CATALOG:
        grouped.setdefault(tool.category, []).append(tool)

    lines = ["Tool catalog:"]
    for category in CATEGORY_ORDER:
        tools = grouped.get(category, [])
        if not tools:
            continue
        rendered = ", ".join(f"{tool.name} - {tool.description}" for tool in tools)
        lines.append(f"{category}: {rendered}")
    lines.append("Tool selection rules:")
    lines.extend(f"- {rule}" for rule in TOOL_SELECTION_RULES)
    lines.append("MCP tools are prefixed mcp__{server}__{tool}.")
    return "\n".join(lines)
