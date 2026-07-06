from __future__ import annotations

import glob as globlib
import fnmatch
import mimetypes
import subprocess
from pathlib import Path
from typing import Iterable

from codeagent.tools.results import EvidenceItem, ToolResult, first_quote

BINARY_TOOL_HINTS = {
    ".xlsx": "Use spreadsheet_read for Excel files (legacy: read_spreadsheet).",
    ".xls": "Use spreadsheet_read for Excel files (legacy: read_spreadsheet).",
    ".pdf": "Use pdf_extract_text or pdf_extract_tables for PDF files (legacy: extract_pdf_text/extract_pdf_tables).",
    ".mp3": "Use audio_transcribe for audio files (legacy: transcribe_audio).",
    ".wav": "Use audio_transcribe for audio files (legacy: transcribe_audio).",
    ".m4a": "Use audio_transcribe for audio files (legacy: transcribe_audio).",
    ".png": "Use image_ocr for image files (legacy: ocr_image).",
    ".jpg": "Use image_ocr for image files (legacy: ocr_image).",
    ".jpeg": "Use image_ocr for image files (legacy: ocr_image).",
    ".webp": "Use image_ocr for image files (legacy: ocr_image).",
}

TEXT_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".yaml", ".yml", ".html", ".xml"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls"}
PDF_EXTENSIONS = {".pdf"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


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
        fp = safe_path(path, cwd)
        suffix = fp.suffix.lower()
        if suffix in BINARY_TOOL_HINTS:
            return f"Error: binary or structured file detected ({suffix}). {BINARY_TOOL_HINTS[suffix]}"

        text = None
        last_error: Exception | None = None
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                text = fp.read_text(encoding=encoding)
                break
            except UnicodeDecodeError as exc:
                last_error = exc
        if text is None:
            return f"Error: could not decode text file: {last_error}"

        lines = text.splitlines()
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


def detect_file_type(path: str) -> str:
    suffix = Path(str(path)).suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if suffix in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in IMAGE_EXTENSIONS:
        return "image"

    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        return "unknown_binary"
    if mime.startswith("text/") or mime in {"application/json", "application/xml"}:
        return "text"
    if mime in {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        return "spreadsheet"
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("image/"):
        return "image"
    return "unknown_binary"


def list_dir(path: str, cwd: Path, limit: int = 200) -> ToolResult:
    try:
        root = safe_path(path or ".", cwd)
        if not root.exists():
            return ToolResult(ok=False, error_type="path_not_found", content=f"Path not found: {path}")
        if not root.is_dir():
            return ToolResult(ok=False, error_type="not_a_directory", content=f"Not a directory: {path}")

        entries = sorted(root.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:limit]
        lines = [f"Directory: {root}"]
        for entry in entries:
            kind = "dir" if entry.is_dir() else detect_file_type(str(entry))
            size = "" if entry.is_dir() else f" {entry.stat().st_size} bytes"
            lines.append(f"{kind:16} {entry.name}{size}")
        return ToolResult(ok=True, content="\n".join(lines), metadata={"path": str(root), "count": len(entries)})
    except Exception as exc:
        return ToolResult(ok=False, error_type="file_parse_failed", content=str(exc), metadata={"path": path})


def find_files(root: str, pattern: str, cwd: Path, limit: int = 500) -> ToolResult:
    try:
        base = safe_path(root or ".", cwd)
        if not base.is_dir():
            return ToolResult(ok=False, error_type="not_a_directory", content=f"Not a directory: {root}")
        matches: list[str] = []
        for path in base.rglob(pattern or "*"):
            if path.resolve().is_relative_to(cwd.resolve()):
                matches.append(str(path))
            if len(matches) >= limit:
                break
        content = "\n".join(matches) if matches else "(no matches)"
        return ToolResult(
            ok=bool(matches),
            error_type=None if matches else "empty_search_results",
            content=content,
            metadata={"root": str(base), "pattern": pattern, "count": len(matches)},
        )
    except Exception as exc:
        return ToolResult(ok=False, error_type="file_parse_failed", content=str(exc), metadata={"root": root, "pattern": pattern})


def _iter_search_files(root: Path, include_globs: Iterable[str] | None) -> Iterable[Path]:
    globs = list(include_globs or ["*"])
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        if any(fnmatch.fnmatch(path.name, glob) or fnmatch.fnmatch(rel, glob) for glob in globs):
            yield path


def _read_text_for_search(path: Path) -> str | None:
    if detect_file_type(str(path)) != "text":
        return None
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except Exception:
            return None
    return None


def search_text(
    root: str,
    query: str,
    cwd: Path,
    include_globs: list[str] | None = None,
    limit: int = 100,
) -> ToolResult:
    try:
        base = safe_path(root or ".", cwd)
        if not base.is_dir():
            return ToolResult(ok=False, error_type="not_a_directory", content=f"Not a directory: {root}")
        needle = str(query or "")
        if not needle:
            return ToolResult(ok=False, error_type="invalid_input", content="query is required.")
        matches: list[str] = []
        for path in _iter_search_files(base, include_globs):
            text = _read_text_for_search(path)
            if text is None:
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                if needle.lower() in line.lower():
                    matches.append(f"{path}:{line_number}: {line.strip()}")
                    break
            if len(matches) >= limit:
                break
        content = "\n".join(matches) if matches else "(no matches)"
        return ToolResult(
            ok=bool(matches),
            error_type=None if matches else "empty_search_results",
            content=content,
            metadata={"root": str(base), "query": needle, "count": len(matches)},
            evidence=[
                EvidenceItem(
                    tool_name="text_search",
                    source=str(base),
                    summary=f"Found {len(matches)} text match(es) for '{needle}'.",
                    quote=first_quote(content),
                )
            ]
            if matches
            else [],
        )
    except Exception as exc:
        return ToolResult(ok=False, error_type="file_parse_failed", content=str(exc), metadata={"root": root, "query": query})
