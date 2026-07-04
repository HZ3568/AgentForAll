from __future__ import annotations

from pathlib import Path

from codeagent.core import config as config_module
from codeagent.core.runtime import create_runtime


def test_create_runtime_uses_configured_memory_dir(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "load_dotenv", lambda override=True: None)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "workdir: conversation-workspace\nmemory_dir: user-state/.memory\n",
        encoding="utf-8",
    )

    runtime = create_runtime(str(config_path))

    assert runtime.settings.workdir == (tmp_path / "conversation-workspace").resolve()
    assert runtime.settings.memory_dir == (tmp_path / "user-state" / ".memory").resolve()
    assert runtime.memory.memory_dir == (tmp_path / "user-state" / ".memory").resolve()
    assert runtime.tasks.tasks_dir == runtime.settings.workdir / ".tasks"
