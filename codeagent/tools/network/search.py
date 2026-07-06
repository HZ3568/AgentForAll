from __future__ import annotations

import os
import urllib.parse
from html.parser import HTMLParser
from typing import Any

import requests

from codeagent.core.config import WebSearchSettings
from codeagent.tools.results import (
    EvidenceItem,
    SearchResult,
    ToolResult,
    classify_http_error,
    first_quote,
    is_tool_failure,
    summarize_text,
)
from codeagent.tools.network.fetch import _decode_bytes, _html_to_text, _read_url


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[SearchResult] = []
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

        url = _normalize_duckduckgo_url(href)
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
        if title and not any(result.url == self.current_url for result in self.results):
            self.results.append(
                SearchResult(
                    title=title,
                    url=self.current_url,
                    snippet="",
                    source="duckduckgo",
                )
            )
        self.current_url = None
        self.current_title = []


def _normalize_duckduckgo_url(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = urllib.parse.urljoin("https://duckduckgo.com", href)

    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    return href


def _settings_from_any(settings: Any | None) -> WebSearchSettings:
    if isinstance(settings, WebSearchSettings):
        return settings
    if settings is None:
        return WebSearchSettings()
    return WebSearchSettings(
        provider=str(getattr(settings, "provider", "disabled")),
        timeout_seconds=int(getattr(settings, "timeout_seconds", 20)),
        max_results=int(getattr(settings, "max_results", 5)),
    )


def _results_to_tool_result(query: str, provider: str, results: list[SearchResult]) -> ToolResult:
    if not results:
        return ToolResult(
            ok=False,
            error_type="empty_search_results",
            content=f"No search results for query: {query}",
            metadata={"query": query, "provider": provider},
        )

    lines = [f"Search query: {query}", f"Provider: {provider}", ""]
    for index, result in enumerate(results, 1):
        lines.append(f"{index}. {result.title}")
        lines.append(f"   URL: {result.url}")
        if result.snippet:
            lines.append(f"   Snippet: {result.snippet}")

    content = "\n".join(lines)
    return ToolResult(
        ok=True,
        content=content,
        metadata={
            "query": query,
            "provider": provider,
            "results": [result.__dict__ for result in results],
        },
        evidence=[
            EvidenceItem(
                tool_name="web_search",
                source=result.url,
                summary=f"Search result: {result.title}",
                quote=result.snippet or result.title,
                metadata={"provider": provider, "query": query},
            )
            for result in results
        ],
    )


def _missing_key(provider: str, env_name: str) -> ToolResult:
    return ToolResult(
        ok=False,
        error_type="missing_api_key",
        content=f"Web search provider '{provider}' is configured but {env_name} is missing.",
        metadata={"provider": provider, "env": env_name},
    )


def _request_json(
    method: str,
    url: str,
    timeout: int,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_body,
        timeout=timeout,
    )
    failure = classify_http_error(response.status_code)
    if failure:
        raise requests.HTTPError(failure, response=response)
    response.raise_for_status()
    return response.json(), response.status_code


def _brave_search(query: str, settings: WebSearchSettings) -> ToolResult:
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return _missing_key("brave", "BRAVE_SEARCH_API_KEY")

    try:
        payload, status = _request_json(
            "GET",
            "https://api.search.brave.com/res/v1/web/search",
            settings.timeout_seconds,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": settings.max_results},
        )
    except requests.HTTPError as exc:
        error_type = str(exc) or "fetch_failed"
        return ToolResult(
            ok=False,
            error_type=error_type,
            content=f"Brave Search failed: {error_type}",
            metadata={"provider": "brave", "query": query},
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="fetch_failed",
            content=f"Brave Search failed: {type(exc).__name__}: {exc}",
            metadata={"provider": "brave", "query": query},
        )

    web_results = payload.get("web", {}).get("results", []) or []
    results = [
        SearchResult(
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            snippet=str(item.get("description") or ""),
            source="brave",
        )
        for item in web_results
        if item.get("url")
    ][: settings.max_results]
    result = _results_to_tool_result(query, "brave", results)
    result.metadata["status"] = status
    return result


def _tavily_search(query: str, settings: WebSearchSettings) -> ToolResult:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return _missing_key("tavily", "TAVILY_API_KEY")

    try:
        payload, status = _request_json(
            "POST",
            "https://api.tavily.com/search",
            settings.timeout_seconds,
            json_body={
                "api_key": api_key,
                "query": query,
                "max_results": settings.max_results,
                "search_depth": "basic",
                "include_answer": False,
            },
        )
    except requests.HTTPError as exc:
        error_type = str(exc) or "fetch_failed"
        return ToolResult(
            ok=False,
            error_type=error_type,
            content=f"Tavily search failed: {error_type}",
            metadata={"provider": "tavily", "query": query},
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="fetch_failed",
            content=f"Tavily search failed: {type(exc).__name__}: {exc}",
            metadata={"provider": "tavily", "query": query},
        )

    results = [
        SearchResult(
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            snippet=str(item.get("content") or ""),
            source="tavily",
        )
        for item in payload.get("results", []) or []
        if item.get("url")
    ][: settings.max_results]
    result = _results_to_tool_result(query, "tavily", results)
    result.metadata["status"] = status
    return result


def _duckduckgo_search(query: str, settings: WebSearchSettings) -> ToolResult:
    search_url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        data, content_type, status, final_url = _read_url(
            search_url,
            settings.timeout_seconds,
            max_bytes=3_000_000,
        )
        failure = classify_http_error(status)
        if failure:
            return ToolResult(
                ok=False,
                error_type=failure,
                content=f"DuckDuckGo returned HTTP {status}",
                metadata={"provider": "duckduckgo", "query": query, "url": final_url},
            )

        markup = _decode_bytes(data, content_type)
        failed, error_type = is_tool_failure(markup)
        if failed:
            return ToolResult(
                ok=False,
                error_type=error_type,
                content=summarize_text(_html_to_text(markup, 1500), 1500),
                metadata={"provider": "duckduckgo", "query": query, "url": final_url},
            )

        parser = _DuckDuckGoResultParser()
        parser.feed(markup)
        results = parser.results[: settings.max_results]
        result = _results_to_tool_result(query, "duckduckgo", results)
        result.metadata["status"] = status
        result.metadata["url"] = final_url
        return result
    except Exception as exc:
        return ToolResult(
            ok=False,
            error_type="fetch_failed",
            content=f"DuckDuckGo search failed: {type(exc).__name__}: {exc}",
            metadata={"provider": "duckduckgo", "query": query},
        )


def run_web_search(
    query: str,
    settings: WebSearchSettings | Any | None = None,
    max_results: int | None = None,
    timeout: int | None = None,
) -> ToolResult:
    query = str(query or "").strip()
    if not query:
        return ToolResult(ok=False, error_type="invalid_input", content="query is required.")

    resolved = _settings_from_any(settings)
    if max_results is not None:
        resolved.max_results = max(1, min(int(max_results), 10))
    if timeout is not None:
        resolved.timeout_seconds = max(1, min(int(timeout), 60))

    provider = resolved.provider.lower().strip()
    if provider == "disabled":
        return ToolResult(
            ok=False,
            error_type="provider_disabled",
            content="Web search is disabled. Configure web_search.provider and an API key.",
            metadata={"provider": provider, "query": query},
        )
    if provider == "brave":
        return _brave_search(query, resolved)
    if provider == "tavily":
        return _tavily_search(query, resolved)
    if provider == "duckduckgo":
        return _duckduckgo_search(query, resolved)
    if provider in {"serpapi", "bing"}:
        return ToolResult(
            ok=False,
            error_type="provider_not_implemented",
            content=f"Web search provider '{provider}' is reserved but not implemented yet.",
            metadata={"provider": provider, "query": query},
        )

    return ToolResult(
        ok=False,
        error_type="unknown_provider",
        content=f"Unknown web search provider: {provider}",
        metadata={"provider": provider, "query": query},
    )
