from __future__ import annotations

from pathlib import Path

from scripts.migrate_runtime_memory import apply_migration, plan_migration


def write_memory(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_memory_migration_plan_ignores_index_and_does_not_write_on_dry_run(tmp_path: Path):
    root = tmp_path / ".runtime_workspaces"
    legacy_dir = root / "user_u1" / "conv_c1" / ".memory"
    write_memory(legacy_dir / "MEMORY.md", "- [legacy](legacy.md)\n")
    write_memory(legacy_dir / "legacy.md", "---\nname: legacy\ndescription: Legacy.\ntype: user\n---\n\nBody.\n")

    actions = plan_migration(root)

    assert len(actions) == 1
    assert actions[0].destination == root / "user_u1" / ".memory" / "legacy.md"
    assert not (root / "user_u1" / ".memory").exists()


def test_memory_migration_apply_copies_and_rebuilds_index(tmp_path: Path):
    root = tmp_path / ".runtime_workspaces"
    write_memory(
        root / "user_u1" / "conv_c1" / ".memory" / "legacy.md",
        "---\nname: legacy\ndescription: Legacy memory.\ntype: user\n---\n\nBody.\n",
    )

    touched = apply_migration(plan_migration(root))

    user_memory = root / "user_u1" / ".memory"
    assert touched == [user_memory]
    assert (user_memory / "legacy.md").exists()
    assert "Legacy memory." in (user_memory / "MEMORY.md").read_text(encoding="utf-8")


def test_memory_migration_conflict_uses_conversation_prefix(tmp_path: Path):
    root = tmp_path / ".runtime_workspaces"
    write_memory(root / "user_u1" / ".memory" / "same.md", "existing")
    write_memory(root / "user_u1" / "conv_abcdef123456789" / ".memory" / "same.md", "new")

    actions = plan_migration(root)

    assert len(actions) == 1
    assert actions[0].destination.name == "conv_abcdef12__same.md"


def test_memory_migration_planned_conflicts_do_not_overwrite(tmp_path: Path):
    root = tmp_path / ".runtime_workspaces"
    write_memory(root / "user_u1" / "conv_abcdef123456789" / ".memory" / "same.md", "first")
    write_memory(root / "user_u1" / "conv_fedcba987654321" / ".memory" / "same.md", "second")

    actions = plan_migration(root)

    destination_names = sorted(action.destination.name for action in actions)
    assert destination_names == ["conv_fedcba98__same.md", "same.md"]

    apply_migration(actions)

    user_memory = root / "user_u1" / ".memory"
    assert (user_memory / "same.md").read_text(encoding="utf-8") == "first"
    assert (user_memory / "conv_fedcba98__same.md").read_text(encoding="utf-8") == "second"
