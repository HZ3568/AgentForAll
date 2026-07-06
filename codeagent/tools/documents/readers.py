from __future__ import annotations

import csv
import fnmatch
import mimetypes
from pathlib import Path
from typing import Iterable

from codeagent.tools.workspace.filesystem import safe_path
from codeagent.tools.results import EvidenceItem, ToolResult, first_quote, summarize_text
from codeagent.tools.network.fetch import run_pdf_extract

TEXT_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".yaml", ".yml", ".html", ".xml"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls"}
PDF_EXTENSIONS = {".pdf"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


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


def _safe_file(path: str, cwd: Path) -> Path:
    fp = safe_path(path, cwd)
    if not fp.exists():
        raise FileNotFoundError(path)
    if fp.is_dir():
        raise IsADirectoryError(path)
    return fp


def read_spreadsheet(
    path: str,
    cwd: Path,
    sheet_name: str | None = None,
    max_rows: int = 20,
) -> ToolResult:
    try:
        fp = _safe_file(path, cwd)
        max_rows = max(1, min(int(max_rows or 20), 200))
        if fp.suffix.lower() == ".csv":
            import pandas as pd

            df = pd.read_csv(fp)
            preview = df.head(max_rows).to_csv(index=False)
            content = (
                f"File: {fp}\n"
                "Type: csv\n"
                f"Rows: {len(df)}\n"
                f"Columns: {len(df.columns)}\n"
                f"Column names: {', '.join(map(str, df.columns))}\n\n"
                f"Preview:\n{preview}"
            )
            return ToolResult(
                ok=True,
                content=content,
                metadata={"path": str(fp), "rows": len(df), "columns": list(map(str, df.columns))},
                evidence=[
                    EvidenceItem(
                        tool_name="spreadsheet_read",
                        source=str(fp),
                        summary=f"Read CSV with {len(df)} rows and {len(df.columns)} columns.",
                        quote=first_quote(preview),
                    )
                ],
            )

        import pandas as pd

        excel = pd.ExcelFile(fp)
        selected_sheet = sheet_name or excel.sheet_names[0]
        if selected_sheet not in excel.sheet_names:
            return ToolResult(
                ok=False,
                error_type="sheet_not_found",
                content=f"Sheet '{selected_sheet}' not found. Available sheets: {', '.join(excel.sheet_names)}",
                metadata={"path": str(fp), "sheets": excel.sheet_names},
            )

        df = pd.read_excel(excel, sheet_name=selected_sheet)
        preview = df.head(max_rows).to_csv(index=False)
        content = (
            f"File: {fp}\n"
            "Type: spreadsheet\n"
            f"Sheets: {', '.join(excel.sheet_names)}\n"
            f"Selected sheet: {selected_sheet}\n"
            f"Rows: {len(df)}\n"
            f"Columns: {len(df.columns)}\n"
            f"Column names: {', '.join(map(str, df.columns))}\n\n"
            f"Preview:\n{preview}"
        )
        return ToolResult(
            ok=True,
            content=content,
            metadata={
                "path": str(fp),
                "sheets": excel.sheet_names,
                "sheet_name": selected_sheet,
                "rows": len(df),
                "columns": list(map(str, df.columns)),
            },
            evidence=[
                EvidenceItem(
                    tool_name="spreadsheet_read",
                    source=str(fp),
                    summary=f"Read sheet '{selected_sheet}' with {len(df)} rows and {len(df.columns)} columns.",
                    quote=first_quote(preview),
                )
            ],
        )
    except ImportError as exc:
        return ToolResult(
            ok=False,
            error_type="missing_spreadsheet_dependency",
            content=f"Missing spreadsheet dependency: {exc}. Install pandas and openpyxl.",
            metadata={"path": path},
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="file_parse_failed",
            content=str(exc),
            metadata={"path": path},
        )


def extract_pdf_text(path: str, cwd: Path, max_pages: int = 20, max_chars: int = 50_000) -> ToolResult:
    return run_pdf_extract(path, cwd, max_pages=max_pages, max_chars=max_chars)


def extract_pdf_tables(path: str, cwd: Path, max_pages: int = 20, max_chars: int = 50_000) -> ToolResult:
    try:
        fp = _safe_file(path, cwd)
        try:
            import pdfplumber
        except ImportError:
            return ToolResult(
                ok=False,
                error_type="missing_pdf_table_dependency",
                content="pdfplumber is not installed. Install it with: pip install pdfplumber",
                metadata={"path": str(fp)},
            )

        pages_out: list[str] = []
        tables_found = 0
        with pdfplumber.open(fp) as pdf:
            page_count = len(pdf.pages)
            for page_index, page in enumerate(pdf.pages[: max(1, min(max_pages, page_count))], 1):
                tables = page.extract_tables() or []
                for table_index, table in enumerate(tables, 1):
                    tables_found += 1
                    pages_out.append(f"[Page {page_index} Table {table_index}]")
                    for row in table[:30]:
                        pages_out.append(" | ".join("" if cell is None else str(cell) for cell in row))
                    if len(table) > 30:
                        pages_out.append(f"... ({len(table) - 30} more rows)")

        if tables_found == 0:
            return ToolResult(
                ok=False,
                error_type="empty_pdf_tables",
                content=f"No tables found in PDF: {fp}",
                metadata={"path": str(fp)},
            )

        body = "\n".join(pages_out)
        if len(body) > max_chars:
            body = body[:max_chars] + "\n...[truncated]"
        content = f"File: {fp}\nTables found: {tables_found}\n\n{body}"
        return ToolResult(
            ok=True,
            content=content,
            metadata={"path": str(fp), "tables_found": tables_found},
            evidence=[
                EvidenceItem(
                    tool_name="pdf_extract_tables",
                    source=str(fp),
                    summary=f"Extracted {tables_found} table(s) from PDF.",
                    quote=first_quote(body),
                )
            ],
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="file_parse_failed",
            content=str(exc),
            metadata={"path": path},
        )


def transcribe_audio(path: str, cwd: Path) -> ToolResult:
    try:
        fp = _safe_file(path, cwd)
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return ToolResult(
                ok=False,
                error_type="missing_audio_dependency",
                content="faster-whisper is not installed. Install optional dependency faster-whisper to transcribe audio.",
                metadata={"path": str(fp)},
            )

        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(fp))
        text = "\n".join(segment.text.strip() for segment in segments if segment.text.strip())
        if not text:
            return ToolResult(
                ok=False,
                error_type="audio_transcription_failed",
                content="No transcription text produced.",
                metadata={"path": str(fp)},
            )
        content = (
            f"File: {fp}\n"
            f"Language: {getattr(info, 'language', 'unknown')}\n"
            f"Duration: {getattr(info, 'duration', 'unknown')}\n\n"
            f"{text}"
        )
        return ToolResult(
            ok=True,
            content=content,
            metadata={"path": str(fp), "language": getattr(info, "language", None)},
            evidence=[
                EvidenceItem(
                    tool_name="audio_transcribe",
                    source=str(fp),
                    summary=summarize_text(text),
                    quote=first_quote(text),
                )
            ],
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="audio_transcription_failed",
            content=str(exc),
            metadata={"path": path},
        )


def ocr_image(path: str, cwd: Path) -> ToolResult:
    try:
        fp = _safe_file(path, cwd)
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return ToolResult(
                ok=False,
                error_type="missing_ocr_dependency",
                content="pytesseract and Pillow are required for OCR. Install pytesseract and configure the Tesseract binary.",
                metadata={"path": str(fp)},
            )

        text = pytesseract.image_to_string(Image.open(fp)).strip()
        if not text:
            return ToolResult(
                ok=False,
                error_type="ocr_failed",
                content="OCR produced no text.",
                metadata={"path": str(fp)},
            )
        return ToolResult(
            ok=True,
            content=f"File: {fp}\n\n{text}",
            metadata={"path": str(fp)},
            evidence=[
                EvidenceItem(
                    tool_name="image_ocr",
                    source=str(fp),
                    summary=summarize_text(text),
                    quote=first_quote(text),
                )
            ],
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="ocr_failed",
            content=str(exc),
            metadata={"path": path},
        )


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
                    tool_name="search_text",
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
