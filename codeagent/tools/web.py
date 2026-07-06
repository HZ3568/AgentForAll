from __future__ import annotations

from codeagent.tools.network import fetch as _fetch
from codeagent.tools.network.fetch import (
    MAX_DOWNLOAD_BYTES,
    USER_AGENT,
    _decode_bytes,
    _html_to_text,
    _read_url,
)

def run_fetch_url(url: str, max_chars: int = 20_000, timeout: int = 20):
    _fetch._read_url = _read_url
    return _fetch.run_fetch_url(url, max_chars, timeout)


def run_pdf_extract(
    source: str,
    cwd,
    max_pages: int | None = 20,
    max_chars: int = 50_000,
    timeout: int = 20,
):
    _fetch._read_url = _read_url
    return _fetch.run_pdf_extract(source, cwd, max_pages, max_chars, timeout)


def run_web_search(query: str, max_results: int = 5, timeout: int = 20) -> str:
    _fetch._read_url = _read_url
    return _fetch.run_web_search(query, max_results, timeout)


__all__ = [
    "MAX_DOWNLOAD_BYTES",
    "USER_AGENT",
    "_decode_bytes",
    "_html_to_text",
    "_read_url",
    "run_fetch_url",
    "run_pdf_extract",
    "run_web_search",
]
