from __future__ import annotations

from codeagent.tools.network import search as _search
from codeagent.tools.network.search import _normalize_duckduckgo_url, _read_url


def run_web_search(query: str, settings=None, max_results: int | None = None, timeout: int | None = None):
    _search._read_url = _read_url
    return _search.run_web_search(query, settings, max_results, timeout)

__all__ = ["_normalize_duckduckgo_url", "_read_url", "run_web_search"]
