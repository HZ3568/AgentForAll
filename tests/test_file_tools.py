from pathlib import Path

import pytest

from codeagent.tools.basic import run_read
from codeagent.tools.file_tools import extract_pdf_tables, ocr_image, transcribe_audio


def test_xlsx_is_not_read_as_utf8(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet["A1"] = "name"
    worksheet["A2"] = "alice"
    workbook.save(tmp_path / "sample.xlsx")

    output = run_read("sample.xlsx", tmp_path)

    assert "binary or structured file detected" in output
    assert "read_spreadsheet" in output


def test_pdf_tables_empty_result_is_explicit(tmp_path: Path):
    pytest.importorskip("pdfplumber")
    pypdf = pytest.importorskip("pypdf")

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf_path = tmp_path / "blank.pdf"
    with pdf_path.open("wb") as f:
        writer.write(f)

    result = extract_pdf_tables("blank.pdf", tmp_path)

    assert not result.ok
    assert result.error_type == "empty_pdf_tables"


def test_missing_audio_dependency_returns_clear_error(tmp_path: Path, monkeypatch):
    audio_path = tmp_path / "sample.mp3"
    audio_path.write_bytes(b"not real audio")

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    result = transcribe_audio("sample.mp3", tmp_path)

    assert not result.ok
    assert result.error_type == "missing_audio_dependency"


def test_missing_ocr_dependency_returns_clear_error(tmp_path: Path, monkeypatch):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"not real image")

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name in {"pytesseract", "PIL"}:
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    result = ocr_image("sample.png", tmp_path)

    assert not result.ok
    assert result.error_type == "missing_ocr_dependency"
