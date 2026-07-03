from __future__ import annotations

import threading
from dataclasses import dataclass, field

from anthropic import Anthropic

from codeagent.agents.bus import MessageBus
from codeagent.agents.protocols import ProtocolRegistry
from codeagent.core.config import Settings, load_settings
from codeagent.hooks.defaults import register_default_hooks
from codeagent.hooks.manager import HookManager
from codeagent.mcp.client import MCPRegistry
from codeagent.memory.skills import SkillRegistry
from codeagent.memory.store import MemoryStore
from codeagent.tasks.background import BackgroundManager
from codeagent.tasks.cron import CronScheduler
from codeagent.tasks.store import TaskStore
from codeagent.tasks.worktree import WorktreeManager
from codeagent.tools.results import EvidenceItem


@dataclass
class Runtime:
    settings: Settings
    client: Anthropic
    hooks: HookManager
    memory: MemoryStore
    skills: SkillRegistry
    tasks: TaskStore
    worktrees: WorktreeManager
    background: BackgroundManager
    cron: CronScheduler
    bus: MessageBus
    protocols: ProtocolRegistry
    mcp: MCPRegistry
    current_todos: list[dict] = field(default_factory=list)
    active_teammates: dict[str, bool] = field(default_factory=dict)
    rounds_since_todo: int = 0
    cli_active: bool = False
    agent_lock: threading.Lock = field(default_factory=threading.Lock)
    mode: str = "default"
    gaia_eval_mode: str = "off"
    current_task_id: str | None = None
    current_scratch_dir: str | None = None
    allow_project_writes: bool = True
    evidence: list[EvidenceItem] = field(default_factory=list)
    tool_errors: list[dict] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)

    def update_context(self, context: dict | None = None, messages: list | None = None) -> dict:
        del context
        return {
            "memories": self.memory.build_context(
                messages or [],
                client=self.client,
                model=self.settings.model_id,
            ),
            "connected_mcp": self.mcp.connected_names(),
            "active_teammates": list(self.active_teammates.keys()),
            "os_name": self.settings.os_name,
            "shell_name": self.settings.shell_name,
            "mode": self.mode,
            "gaia_eval_mode": self.gaia_eval_mode,
            "scratch_dir": self.current_scratch_dir,
        }

    def reset_tool_tracking(self) -> None:
        self.evidence.clear()
        self.tool_errors.clear()
        self.tools_used.clear()

    def start_services(self) -> None:
        self.cron.start()


def create_runtime(config_path: str | None = None) -> Runtime:
    settings = load_settings(config_path)
    settings.workdir.mkdir(parents=True, exist_ok=True)
    client = Anthropic(base_url=settings.anthropic_base_url)
    tasks = TaskStore(settings.workdir)
    bus = MessageBus(settings.workdir)
    runtime = Runtime(
        settings=settings,
        client=client,
        hooks=HookManager(),
        memory=MemoryStore(settings.workdir),
        skills=SkillRegistry(settings.workdir),
        tasks=tasks,
        worktrees=WorktreeManager(settings.workdir, tasks),
        background=BackgroundManager(),
        cron=CronScheduler(settings.workdir),
        bus=bus,
        protocols=ProtocolRegistry(bus),
        mcp=MCPRegistry(),
        mode=settings.mode,
    )
    register_default_hooks(runtime)
    runtime.start_services()
    return runtime
