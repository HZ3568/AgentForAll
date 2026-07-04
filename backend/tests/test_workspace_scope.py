from __future__ import annotations

import yaml

from backend.app.runtime.agent_adapter import AgentRuntimeAdapter
from backend.app.runtime.session_manager import AgentSessionManager


class FakeRuntime:
    current_scratch_dir = None

    def reset_tool_tracking(self) -> None:
        return None

    def update_context(self, context=None, messages=None):
        del context, messages
        return {}


def test_session_manager_creates_user_memory_and_conversation_workspace(tmp_path):
    manager = AgentSessionManager(adapter=AgentRuntimeAdapter(), workspace_root=tmp_path)

    workspace = manager.prepare_workspace("user-1", "conv-1")

    assert workspace == tmp_path / "user_user-1" / "conv_conv-1"
    assert (tmp_path / "user_user-1" / ".memory").is_dir()
    assert (workspace / "scratch").is_dir()
    assert not (workspace / ".memory").exists()


def test_adapter_writes_workdir_and_user_memory_dir(tmp_path):
    config_paths: list[str | None] = []

    def fake_runtime_factory(config_path: str | None):
        config_paths.append(config_path)
        return FakeRuntime()

    def fake_loop(runtime, messages, context):
        del runtime, context
        messages.append({"role": "assistant", "content": "ok"})

    adapter = AgentRuntimeAdapter(runtime_factory=fake_runtime_factory, loop_runner=fake_loop)
    workspace = tmp_path / "user_user-1" / "conv_conv-1"
    memory = tmp_path / "user_user-1" / ".memory"

    result = adapter.run_turn(
        conversation_id="conv-1",
        user_id="user-1",
        history=[],
        user_message={"role": "user", "content_text": "hi"},
        workspace_path=str(workspace),
        memory_path=str(memory),
    )

    assert result.final_text == "ok"
    config = yaml.safe_load((workspace / "codeagent_web_config.yaml").read_text(encoding="utf-8"))
    assert config["workdir"] == str(workspace)
    assert config["memory_dir"] == str(memory)
    assert config_paths == [str(workspace / "codeagent_web_config.yaml")]
