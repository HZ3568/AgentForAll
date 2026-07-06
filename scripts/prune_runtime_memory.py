from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codeagent.memory.store import MemoryStore, looks_like_transient_task_memory


@dataclass(frozen=True, slots=True)
class PruneAction:
    source: Path
    destination: Path
    reason: str


def plan_prune(workspace_root: Path, timestamp: str | None = None) -> list[PruneAction]:
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    actions: list[PruneAction] = []
    for memory_dir in _iter_user_memory_dirs(workspace_root):
        quarantine_dir = memory_dir.parent / ".memory_quarantine" / stamp
        for path in sorted(memory_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            text = path.read_text(encoding="utf-8")
            if looks_like_transient_task_memory(text):
                actions.append(
                    PruneAction(
                        source=path,
                        destination=_unique_destination(quarantine_dir / path.name),
                        reason="transient task progress memory",
                    )
                )
    return actions


def apply_prune(actions: list[PruneAction]) -> list[Path]:
    moved: list[Path] = []
    touched_memory_dirs = sorted({action.source.parent for action in actions})
    for action in actions:
        if not action.source.exists():
            continue
        action.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(action.source), str(action.destination))
        moved.append(action.destination)

    for memory_dir in touched_memory_dirs:
        if memory_dir.exists():
            MemoryStore(memory_dir.parent, memory_dir=memory_dir).rebuild_index()
    return moved


def _iter_user_memory_dirs(workspace_root: Path) -> list[Path]:
    root = workspace_root.resolve()
    if root.name == ".memory" and root.is_dir():
        return [root]
    if not root.exists():
        return []
    return [
        path
        for path in sorted(root.glob("user_*/.memory"))
        if path.is_dir() and path.resolve().is_relative_to(root)
    ]


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quarantine transient task memories from runtime memory dirs."
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(".runtime_workspaces"),
        help="Runtime workspace root or a single .memory directory.",
    )
    parser.add_argument("--apply", action="store_true", help="Move matching files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    actions = plan_prune(args.workspace_root)
    mode = "apply" if args.apply else "dry-run"
    print(f"[{mode}] transient memories matched: {len(actions)}")
    for action in actions:
        print(f"{action.source} -> {action.destination} ({action.reason})")
    if args.apply:
        moved = apply_prune(actions)
        print(f"moved: {len(moved)}")


if __name__ == "__main__":
    main()
