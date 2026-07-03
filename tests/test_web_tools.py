from pathlib import Path

import pytest

from codeagent.tools.registry import BUILTIN_TOOLS
from codeagent.tools.web import _html_to_text, run_fetch_url, run_pdf_extract
from codeagent.tools.web_search import _normalize_duckduckgo_url, run_web_search
from codeagent.core.config import WebSearchSettings


def test_web_tools_are_registered():
    names = {tool["name"] for tool in BUILTIN_TOOLS}
    assert {
        "web_search",
        "fetch_url",
        "pdf_extract",
        "read_spreadsheet",
        "extract_pdf_tables",
    } <= names


def test_html_to_text_removes_scripts():
    html = "<html><head><script>ignore()</script></head><body><h1>Title</h1><p>Hello <b>world</b>.</p></body></html>"
    text = _html_to_text(html)

    assert "Title" in text
    assert "Hello world ." in text
    assert "ignore" not in text


def test_normalize_duckduckgo_redirect_url():
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa%3Fx%3D1"
    assert _normalize_duckduckgo_url(href) == "https://example.com/a?x=1"


def test_pdf_extract_blocks_path_escape(tmp_path: Path):
    output = run_pdf_extract("../secret.pdf", tmp_path)
    assert not output.ok
    assert output.error_type == "file_parse_failed"


def test_duckduckgo_antibot_is_failure(monkeypatch):
    def fake_read_url(url, timeout, max_bytes=20_000_000):
        del url, timeout, max_bytes
        return (
            b"Unfortunately, bots use DuckDuckGo too. Please complete the following challenge.",
            "text/html",
            202,
            "https://duckduckgo.com/html/?q=x",
        )

    monkeypatch.setattr("codeagent.tools.web_search._read_url", fake_read_url)
    result = run_web_search("x", WebSearchSettings(provider="duckduckgo"))

    assert not result.ok
    assert result.error_type == "captcha_blocked"


@pytest.mark.parametrize("status,expected", [(403, "http_403"), (429, "rate_limited")])
def test_fetch_url_http_errors_are_failures(monkeypatch, status, expected):
    def fake_read_url(url, timeout, max_bytes=20_000_000):
        del timeout, max_bytes
        return (b"blocked", "text/html", status, url)

    monkeypatch.setattr("codeagent.tools.web._read_url", fake_read_url)
    result = run_fetch_url("https://example.com")

    assert not result.ok
    assert result.error_type == expected


def test_empty_search_results_are_failure(monkeypatch):
    def fake_read_url(url, timeout, max_bytes=20_000_000):
        del url, timeout, max_bytes
        return (b"<html><body>No results here</body></html>", "text/html", 200, "https://duckduckgo.com/html")

    monkeypatch.setattr("codeagent.tools.web_search._read_url", fake_read_url)
    result = run_web_search("nope", WebSearchSettings(provider="duckduckgo"))

    assert not result.ok
    assert result.error_type == "empty_search_results"


def test_configured_provider_without_key_fails(monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    result = run_web_search("x", WebSearchSettings(provider="brave"))

    assert not result.ok
    assert result.error_type == "missing_api_key"
