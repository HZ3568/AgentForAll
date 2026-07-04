from pathlib import Path

from codeagent.tasks.store import TaskStore


def test_task_dependencies(tmp_path: Path):
    store = TaskStore(tmp_path)
    assert not (tmp_path / ".tasks").exists()
    first = store.create("first")
    assert (tmp_path / ".tasks").exists()
    second = store.create("second", blockedBy=[first.id])
    assert not store.can_start(second.id)
    assert "Claimed" in store.claim(first.id, "tester")
    assert "Completed" in store.complete(first.id)
    assert store.can_start(second.id)
