from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AgentForAll FastAPI backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable development auto-reload.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    reload_dirs = [
        str(repo_root / "backend"),
        str(repo_root / "codeagent"),
    ]
    reload_excludes = [
        ".runtime_workspaces/*",
        ".memory/*",
        ".sessions/*",
        ".tasks/*",
        ".transcripts/*",
        "frontend/node_modules/*",
        "frontend/dist/*",
    ]

    uvicorn.run(
        "backend.app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        reload_dirs=reload_dirs if not args.no_reload else None,
        reload_excludes=reload_excludes if not args.no_reload else None,
    )


if __name__ == "__main__":
    main()
