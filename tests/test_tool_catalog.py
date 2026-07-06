from __future__ import annotations

from types import SimpleNamespace

from codeagent.core.prompt import assemble_system_prompt
from codeagent.tasks.background import BackgroundManager
from codeagent.tools.catalog import LEGACY_TOOL_ALIASES, TOOL_CATALOG, render_tool_guidance
from codeagent.tools.registry import BUILTIN_TOOLS, build_builtin_handlers


def test_builtin_tools_expose_canonical_names_only():
    names = {tool["name"] for tool in BUILTIN_TOOLS}

    assert "shell_run" in names
    assert "file_read" in names
    assert "web_fetch" in names
    assert "spreadsheet_read" in names
    assert "todo_set" in names
    assert "subagent_run" in names
    assert "mcp_connect" in names
    assert "bash" not in names
    assert "read_file" not in names
    assert "fetch_url" not in names
    assert "todo_write" not in names


def test_catalog_entries_have_categories_and_schema():
    catalog_by_name = {tool.name: tool for tool in TOOL_CATALOG}

    assert catalog_by_name["shell_run"].category == "workspace"
    assert catalog_by_name["web_search"].category == "web"
    assert catalog_by_name["pdf_extract_text"].category == "documents"
    assert catalog_by_name["teammate_spawn"].category == "collaboration"

    for tool in TOOL_CATALOG:
        assert tool.description
        assert tool.input_schema["type"] == "object"


def test_legacy_alias_handlers_remain_callable(tmp_path):
    runtime = SimpleNamespace(
        settings=SimpleNamespace(workdir=tmp_path, web_search=None),
        mode="default",
        allow_project_writes=True,
        current_todos=[],
        skills=SimpleNamespace(load=lambda name: f"loaded {name}"),
    )

    handlers = build_builtin_handlers(runtime)

    assert LEGACY_TOOL_ALIASES["bash"] == "shell_run"
    assert "shell_run" in handlers
    assert "bash" in handlers
    assert handlers["bash"]("echo alias").startswith("STDOUT:")
    assert handlers["read_file"]("missing.txt").startswith("Error:")


def test_tool_guidance_groups_categories_and_selection_rules():
    guidance = render_tool_guidance()

    assert "workspace:" in guidance
    assert "web:" in guidance
    assert "documents:" in guidance
    assert "实时公共信息先使用 web_search" in guidance
    assert "代码库检索优先使用 file_find/text_search/file_read" in guidance
    assert "写文件前先用 file_read" in guidance


def test_system_prompt_uses_catalog_guidance(tmp_path):
    runtime = SimpleNamespace(
        settings=SimpleNamespace(workdir=tmp_path, os_name="Windows", shell_name="powershell"),
        skills=SimpleNamespace(list=lambda: "(none)"),
        mcp=SimpleNamespace(connected_names=lambda: []),
        active_teammates={},
    )

    prompt = assemble_system_prompt(runtime, {"os_name": "Windows", "shell_name": "powershell"})

    assert "Tool catalog:" in prompt
    assert "shell_run" in prompt
    assert "web_fetch" in prompt
    assert "Available tools: bash" not in prompt


def test_background_manager_treats_shell_run_like_legacy_bash():
    manager = BackgroundManager()

    assert manager.is_slow_operation("shell_run", {"command": "pytest -q"})
    assert manager.should_run("shell_run", {"run_in_background": True, "command": "echo hi"})
    assert manager.is_slow_operation("bash", {"command": "pytest -q"})
