from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from codeagent.memory.store import MemoryStore
from scripts.prune_runtime_memory import apply_prune, plan_prune


def test_prune_runtime_memory_quarantines_transient_task_memories(tmp_path: Path):
    user_dir = tmp_path / "user_u1"
    memory_dir = user_dir / ".memory"
    store = MemoryStore(user_dir, memory_dir=memory_dir)
    transient = store.write_memory_file(
        "segment-tree-request",
        "user",
        "User requested C++ implementation of segment tree with correctness testing.",
        "The user asked for segment tree implementation and tests.",
    )
    durable = store.write_memory_file(
        "user-prefers-concise",
        "user",
        "User prefers concise final answers.",
        "Keep final answers short unless detail is requested.",
    )

    actions = plan_prune(tmp_path)

    assert [action.source for action in actions] == [transient]
    assert actions[0].destination.parent.parent == user_dir / ".memory_quarantine"

    moved = apply_prune(actions)

    assert moved == [actions[0].destination]
    assert not transient.exists()
    assert actions[0].destination.exists()
    assert durable.exists()
    index = (memory_dir / "MEMORY.md").read_text(encoding="utf-8")
    assert "segment-tree-request" not in index
    assert "user-prefers-concise" in index


def test_prune_runtime_memory_cli_runs_from_repo_root(tmp_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/prune_runtime_memory.py",
            "--workspace-root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 0
    assert "[dry-run] transient memories matched: 0" in result.stdout
