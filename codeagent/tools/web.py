from __future__ import annotations

import html
import io
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from codeagent.tools.basic import safe_path
from codeagent.tools.results import (
    EvidenceItem,
    ToolResult,
    classify_http_error,
    first_quote,
    is_tool_failure,
    summarize_text,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 CodeAgent-Harness/1.0"
)
MAX_DOWNLOAD_BYTES = 20_000_000


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"


def _coerce_int(value: int | str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value) if value is not None else default
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _is_url(value: str) -> bool:
    return urllib.parse.urlparse(value).scheme in {"http", "https"}


def _read_url(url: str, timeout: int, max_bytes: int = MAX_DOWNLOAD_BYTES) -> tuple[bytes, str, int, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are supported.")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"Response exceeds {max_bytes} bytes.")
        content_type = response.headers.get("Content-Type", "")
        status = int(getattr(response, "status", 0) or 0)
        final_url = response.geturl()
    return data, content_type, status, final_url


def _charset_from_content_type(content_type: str) -> str | None:
    match = re.search(r"charset=([\w.-]+)", content_type, re.IGNORECASE)
    return match.group(1) if match else None


def _decode_bytes(data: bytes, content_type: str = "") -> str:
    encodings = [_charset_from_content_type(content_type), "utf-8", "gb18030", "latin-1"]
    for encoding in encodings:
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class _TextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "article",
        "blockquote",
        "br",
        "dd",
        "div",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "main",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth == 0 and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth == 0 and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text + " ")

    def get_text(self) -> str:
        text = html.unescape("".join(self.parts))
        lines = [" ".join(line.split()) for line in text.splitlines()]
        compacted: list[str] = []
        blank = False
        for line in lines:
            if not line:
                if not blank:
                    compacted.append("")
                blank = True
                continue
            compacted.append(line)
            blank = False
        return "\n".join(compacted).strip()


def _html_to_text(markup: str, max_chars: int = 20_000) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    return _clip(parser.get_text(), max_chars)


def _normalize_search_url(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = urllib.parse.urljoin("https://duckduckgo.com", href)

    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    return href


class _SearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self.current_url: str | None = None
        self.current_title: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a" or self.current_url:
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        href = attr_map.get("href", "")
        class_name = attr_map.get("class", "")
        if "result__a" not in class_name and "uddg=" not in href:
            return

        url = _normalize_search_url(href)
        netloc = urllib.parse.urlparse(url).netloc.lower()
        if not url or netloc.endswith("duckduckgo.com"):
            return
        self.current_url = url
        self.current_title = []

    def handle_data(self, data: str) -> None:
        if self.current_url:
            text = " ".join(data.split())
            if text:
                self.current_title.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.current_url:
            return
        title = " ".join(self.current_title).strip()
        if title and not any(result["url"] == self.current_url for result in self.results):
            self.results.append({"title": title, "url": self.current_url})
        self.current_url = None
        self.current_title = []


def run_web_search(query: str, max_results: int = 5, timeout: int = 20) -> str:
    """Search the public web through DuckDuckGo's HTML endpoint."""
    query = str(query or "").strip()
    if not query:
        return "Error: query is required."

    max_results = _coerce_int(max_results, 5, 1, 10)
    timeout = _coerce_int(timeout, 20, 1, 60)

    search_url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        data, content_type, status, final_url = _read_url(search_url, timeout, max_bytes=3_000_000)
        markup = _decode_bytes(data, content_type)
        parser = _SearchResultParser()
        parser.feed(markup)
        results = parser.results[:max_results]
        if not results:
            text = _html_to_text(markup, 1500)
            return (
                f"Search query: {query}\n"
                f"Status: {status}\n"
                f"Source: {final_url}\n\n"
                f"No search results parsed.\n{text}"
            )

        lines = [
            f"Search query: {query}",
            f"Status: {status}",
            f"Source: {final_url}",
            "",
        ]
        for index, result in enumerate(results, 1):
            lines.append(f"{index}. {result['title']}")
            lines.append(f"   {result['url']}")
        return "\n".join(lines)
    except urllib.error.HTTPError as exc:
        return f"Error: HTTP {exc.code} while searching web: {exc.reason}"
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"


def _looks_like_pdf(source: str, content_type: str) -> bool:
    return "pdf" in content_type.lower() or urllib.parse.urlparse(source).path.lower().endswith(".pdf")


def run_fetch_url(url: str, max_chars: int = 20_000, timeout: int = 20) -> ToolResult:
    """Fetch a URL and return readable text for HTML or plain text content."""
    url = str(url or "").strip()
    if not url:
        return ToolResult(ok=False, error_type="invalid_input", content="url is required.")

    max_chars = _coerce_int(max_chars, 20_000, 1000, 100_000)
    timeout = _coerce_int(timeout, 20, 1, 60)

    try:
        data, content_type, status, final_url = _read_url(url, timeout)
        failure = classify_http_error(status)
        if failure:
            return ToolResult(
                ok=False,
                error_type=failure,
                content=f"HTTP {status} while fetching URL: {final_url}",
                metadata={"url": final_url, "status": status, "content_type": content_type},
            )
        if _looks_like_pdf(final_url, content_type):
            return ToolResult(
                ok=True,
                content=(
                    f"URL: {final_url}\n"
                    f"Status: {status}\n"
                    f"Content-Type: {content_type or '(unknown)'}\n\n"
                    "PDF content detected. Use pdf_extract with this URL to extract text."
                ),
                metadata={"url": final_url, "status": status, "content_type": content_type},
            )

        decoded = _decode_bytes(data, content_type)
        failed, error_type = is_tool_failure(decoded)
        if failed:
            return ToolResult(
                ok=False,
                error_type=error_type,
                content=summarize_text(_html_to_text(decoded, 2000), 2000),
                metadata={"url": final_url, "status": status, "content_type": content_type},
            )
        if "html" in content_type.lower() or "<html" in decoded[:1000].lower():
            body = _html_to_text(decoded, max_chars)
        else:
            body = _clip(decoded.strip(), max_chars)

        if not body:
            return ToolResult(
                ok=False,
                error_type="empty_content",
                content="No text extracted from URL.",
                metadata={"url": final_url, "status": status, "content_type": content_type},
            )

        content = (
            f"URL: {final_url}\n"
            f"Status: {status}\n"
            f"Content-Type: {content_type or '(unknown)'}\n\n"
            f"{body}"
        )
        return ToolResult(
            ok=True,
            content=content,
            metadata={"url": final_url, "status": status, "content_type": content_type},
            evidence=[
                EvidenceItem(
                    tool_name="fetch_url",
                    source=final_url,
                    summary=summarize_text(body),
                    quote=first_quote(body),
                    metadata={"content_type": content_type, "status": status},
                )
            ],
        )
    except urllib.error.HTTPError as exc:
        error_type = classify_http_error(exc.code) or "fetch_failed"
        return ToolResult(
            ok=False,
            error_type=error_type,
            content=f"HTTP {exc.code} while fetching URL: {exc.reason}",
            metadata={"url": url, "status": exc.code},
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="fetch_failed",
            content=f"{type(exc).__name__}: {exc}",
            metadata={"url": url},
        )


def run_pdf_extract(
    source: str,
    cwd: Path,
    max_pages: int | None = 20,
    max_chars: int = 50_000,
    timeout: int = 20,
) -> ToolResult:
    """Extract text from a local PDF path inside the workspace or from an HTTP(S) PDF URL."""
    source = str(source or "").strip()
    if not source:
        return ToolResult(ok=False, error_type="invalid_input", content="source is required.")

    max_pages_value = _coerce_int(max_pages, 20, 1, 500) if max_pages is not None else None
    max_chars = _coerce_int(max_chars, 50_000, 1000, 200_000)
    timeout = _coerce_int(timeout, 20, 1, 120)

    try:
        if _is_url(source):
            data, content_type, status, final_url = _read_url(source, timeout)
            failure = classify_http_error(status)
            if failure:
                return ToolResult(
                    ok=False,
                    error_type=failure,
                    content=f"HTTP {status} while fetching PDF URL.",
                    metadata={"source": source, "url": final_url, "status": status},
                )
            source_label = f"{final_url} (HTTP {status}, {content_type or 'unknown content type'})"
        else:
            path = safe_path(source, cwd)
            data = path.read_bytes()
            source_label = str(path)

        try:
            from pypdf import PdfReader
        except ImportError:
            return ToolResult(
                ok=False,
                error_type="missing_pdf_dependency",
                content="pypdf is not installed. Install it with: pip install pypdf",
                metadata={"source": source},
            )

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            return ToolResult(
                ok=False,
                error_type="encrypted_pdf",
                content="PDF is encrypted and cannot be read without a password.",
                metadata={"source": source},
            )

        total_pages = len(reader.pages)
        page_limit = total_pages if max_pages_value is None else min(max_pages_value, total_pages)
        parts = [
            f"Source: {source_label}",
            f"Pages: {total_pages}",
            f"Extracted pages: {page_limit}",
        ]
        for page_index in range(page_limit):
            text = reader.pages[page_index].extract_text() or ""
            text = text.strip()
            parts.append(f"[Page {page_index + 1}]\n{text if text else '(no text extracted)'}")

        content = _clip("\n\n".join(parts), max_chars)
        extracted_text = "\n".join(parts[3:])
        if not extracted_text.strip() or "(no text extracted)" in extracted_text and len(extracted_text.strip()) < 100:
            return ToolResult(
                ok=False,
                error_type="empty_pdf_text",
                content=content,
                metadata={"source": source_label, "pages": total_pages, "extracted_pages": page_limit},
            )
        return ToolResult(
            ok=True,
            content=content,
            metadata={"source": source_label, "pages": total_pages, "extracted_pages": page_limit},
            evidence=[
                EvidenceItem(
                    tool_name="pdf_extract",
                    source=source_label,
                    summary=f"Extracted text from {page_limit}/{total_pages} PDF pages.",
                    quote=first_quote(extracted_text),
                    metadata={"pages": total_pages, "extracted_pages": page_limit},
                )
            ],
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="file_parse_failed",
            content=str(exc),
            metadata={"source": source},
        )
