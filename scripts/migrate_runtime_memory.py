from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codeagent.memory.store import MemoryStore


@dataclass(frozen=True)
class MemoryMigrationAction:
    source: Path
    destination: Path
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge legacy conversation-scoped runtime memories into user-scoped memory directories.",
    )
    parser.add_argument(
        "--workspace-root",
        default=".runtime_workspaces",
        help="Runtime workspace root. Defaults to .runtime_workspaces.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned copies without writing files. This is the default.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy files and rebuild user-level MEMORY.md indexes.",
    )
    return parser.parse_args()


def plan_migration(workspace_root: Path) -> list[MemoryMigrationAction]:
    root = workspace_root.resolve()
    actions: list[MemoryMigrationAction] = []
    reserved_destinations: set[Path] = set()
    if not root.exists():
        return actions

    for user_dir in sorted(root.glob("user_*")):
        if not user_dir.is_dir():
            continue
        target_memory_dir = user_dir / ".memory"
        for conv_dir in sorted(user_dir.glob("conv_*")):
            legacy_memory_dir = conv_dir / ".memory"
            if not legacy_memory_dir.is_dir():
                continue
            for source in sorted(legacy_memory_dir.glob("*.md")):
                if source.name == "MEMORY.md":
                    continue
                destination, reason = _destination_for(
                    source,
                    target_memory_dir,
                    conv_dir.name,
                    reserved_destinations,
                )
                reserved_destinations.add(destination)
                actions.append(MemoryMigrationAction(source=source, destination=destination, reason=reason))
    return actions


def apply_migration(actions: list[MemoryMigrationAction]) -> list[Path]:
    touched_memory_dirs: set[Path] = set()
    for action in actions:
        action.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(action.source, action.destination)
        touched_memory_dirs.add(action.destination.parent)

    for memory_dir in sorted(touched_memory_dirs):
        user_dir = memory_dir.parent
        MemoryStore(user_dir, memory_dir=memory_dir).rebuild_index()
    return sorted(touched_memory_dirs)


def _destination_for(
    source: Path,
    target_memory_dir: Path,
    conversation_dir_name: str,
    reserved_destinations: set[Path],
) -> tuple[Path, str]:
    destination = target_memory_dir / source.name
    if not destination.exists() and destination not in reserved_destinations:
        return destination, "new"

    if destination.exists():
        try:
            if destination.read_bytes() == source.read_bytes():
                return destination, "same-content-overwrite"
        except OSError:
            pass

    prefix = f"{conversation_dir_name[:13]}__"
    candidate = target_memory_dir / f"{prefix}{source.name}"
    if not candidate.exists() and candidate not in reserved_destinations:
        return candidate, "conflict-prefixed"

    stem = source.stem
    suffix = source.suffix
    counter = 2
    while True:
        candidate = target_memory_dir / f"{prefix}{stem}-{counter}{suffix}"
        if not candidate.exists() and candidate not in reserved_destinations:
            return candidate, "conflict-numbered"
        counter += 1


def main() -> None:
    args = parse_args()
    apply_changes = bool(args.apply)
    root = Path(args.workspace_root)
    actions = plan_migration(root)

    mode = "APPLY" if apply_changes else "DRY-RUN"
    print(f"[{mode}] planned memory copies: {len(actions)}")
    for action in actions:
        print(f"{action.reason}: {action.source} -> {action.destination}")

    if apply_changes:
        touched = apply_migration(actions)
        print(f"rebuilt user memory indexes: {len(touched)}")
    elif not args.dry_run:
        print("No changes written. Pass --apply to copy files.")


if __name__ == "__main__":
    main()
