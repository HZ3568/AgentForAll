from __future__ import annotations

import glob as globlib
import subprocess
from pathlib import Path


def safe_path(path: str, base: Path) -> Path:
    root = base.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Path escapes workspace: {path}")
    return target


def _decode_output(data: bytes | str | None) -> str:
    if data is None:
        return ""

    if isinstance(data, str):
        return data

    # 优先尝试 UTF-8，因为你的 bat 里用了 chcp 65001
    for encoding in ("utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    # 兜底：遇到无法识别的字符直接替换，保证 Agent 不崩溃
    return data.decode("utf-8", errors="replace")


def run_bash(command: str, cwd: Path, run_in_background: bool = False) -> str:
    del run_in_background

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            timeout=120,
        )

        stdout = _decode_output(result.stdout).strip()
        stderr = _decode_output(result.stderr).strip()

        parts: list[str] = []

        if stdout:
            parts.append("STDOUT:\n" + stdout)

        if stderr:
            parts.append("STDERR:\n" + stderr)

        if result.returncode != 0:
            parts.append(f"EXIT_CODE: {result.returncode}")

        if not parts:
            return f"(no output, exit={result.returncode})"

        return ("\n\n".join(parts))[:50000]

    except subprocess.TimeoutExpired as exc:
        stdout = _decode_output(exc.stdout).strip()
        stderr = _decode_output(exc.stderr).strip()

        parts = ["Error: Timeout (120s)"]

        if stdout:
            parts.append("STDOUT:\n" + stdout)

        if stderr:
            parts.append("STDERR:\n" + stderr)

        return ("\n\n".join(parts))[:50000]


def run_read(path: str, cwd: Path, limit: int | None = None, offset: int = 0) -> str:
    try:
        lines = safe_path(path, cwd).read_text(encoding="utf-8").splitlines()
        offset = max(int(offset or 0), 0)
        limit = int(limit) if limit is not None else None
        sliced = lines[offset:]
        if limit is not None and limit < len(sliced):
            sliced = sliced[:limit] + [f"... ({len(sliced) - limit} more lines)"]
        return "\n".join(sliced)
    except Exception as exc:
        return f"Error: {exc}"


def run_write(path: str, content: str, cwd: Path) -> str:
    try:
        fp = safe_path(path, cwd)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_edit(path: str, old_text: str, new_text: str, cwd: Path) -> str:
    try:
        fp = safe_path(path, cwd)
        text = fp.read_text(encoding="utf-8")
        if old_text not in text:
            return f"Error: text not found in {path}"
        fp.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_glob(pattern: str, cwd: Path) -> str:
    try:
        matches: list[str] = []
        for match in globlib.glob(pattern, root_dir=cwd):
            if (cwd / match).resolve().is_relative_to(cwd.resolve()):
                matches.append(match)
        return "\n".join(matches) if matches else "(no matches)"
    except Exception as exc:
        return f"Error: {exc}"
