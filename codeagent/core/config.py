from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class WebSearchSettings:
    provider: str = "disabled"
    timeout_seconds: int = 20
    max_results: int = 5


@dataclass
class Settings:
    workdir: Path
    model_id: str
    primary_model: str
    fallback_model_id: str | None
    anthropic_base_url: str | None
    default_max_tokens: int = 8000
    escalated_max_tokens: int = 16000
    max_retries: int = 3
    max_consecutive_529: int = 2
    max_recovery_retries: int = 2
    base_delay_ms: int = 500
    context_limit: int = 50000
    keep_recent_tool_results: int = 3
    persist_threshold: int = 30000
    continuation_prompt: str = "Continue from the previous response. Do not repeat completed work."
    prompt: str = "\033[36magent >> \033[0m"
    mode: str = "default"
    os_name: str = field(default_factory=platform.system)
    shell_name: str = "powershell"
    web_search: WebSearchSettings = field(default_factory=WebSearchSettings)


def _load_yaml(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a mapping: {path}")
    return data


def _detect_shell_name() -> str:
    if os.getenv("PSModulePath"):
        return "powershell"
    comspec = os.getenv("ComSpec", "").lower()
    if "cmd.exe" in comspec:
        return "cmd"
    shell = os.getenv("SHELL", "")
    return Path(shell).name if shell else "unknown"


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _env_int(default: int, *names: str) -> int:
    value = _first_env(*names)
    if value is None:
        return default
    return int(value)


def _auto_web_search_provider(configured_provider: str | None = None) -> str:
    explicit_provider = _first_env("CODEAGENT_WEB_SEARCH_PROVIDER", "WEB_SEARCH_PROVIDER")
    if explicit_provider:
        return explicit_provider.lower()

    if configured_provider is not None and configured_provider.strip():
        provider = configured_provider.strip().lower()
        if provider != "auto":
            return provider

    if _first_env("BRAVE_SEARCH_API_KEY"):
        return "brave"
    if _first_env("TAVILY_API_KEY"):
        return "tavily"
    if _first_env("SERPAPI_API_KEY"):
        return "serpapi"
    if _first_env("BING_SEARCH_API_KEY"):
        return "bing"
    return "disabled"


def load_settings(config_path: str | Path | None = None) -> Settings:
    load_dotenv(override=True)
    path = Path(config_path) if config_path else Path("config.yaml")
    config = _load_yaml(path)

    if os.getenv("ANTHROPIC_BASE_URL"):
        # Anthropic-compatible reverse proxies normally use ANTHROPIC_API_KEY.
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

    limits = config.get("limits", {}) or {}
    runtime = config.get("runtime", {}) or {}
    web_search = config.get("web_search", {}) or {}
    if not isinstance(web_search, dict):
        web_search = {}

    model_id = os.getenv("MODEL_ID") or config.get("model_id") or "claude-sonnet-4-20250514"
    fallback = os.getenv("FALLBACK_MODEL_ID") or config.get("fallback_model_id")
    base_url = os.getenv("ANTHROPIC_BASE_URL") or config.get("anthropic_base_url")
    workdir = Path(os.getenv("CODEAGENT_WORKDIR") or config.get("workdir") or ".").resolve()
    mode = os.getenv("CODEAGENT_MODE") or str(runtime.get("mode", "default"))
    search_provider = _auto_web_search_provider(
        str(web_search["provider"]) if "provider" in web_search else None
    )
    search_timeout = _env_int(
        int(web_search.get("timeout_seconds", 20)),
        "CODEAGENT_WEB_SEARCH_TIMEOUT_SECONDS",
        "WEB_SEARCH_TIMEOUT_SECONDS",
    )
    search_max_results = _env_int(
        int(web_search.get("max_results", 5)),
        "CODEAGENT_WEB_SEARCH_MAX_RESULTS",
        "WEB_SEARCH_MAX_RESULTS",
    )

    return Settings(
        workdir=workdir,
        model_id=model_id,
        primary_model=model_id,
        fallback_model_id=fallback,
        anthropic_base_url=base_url,
        default_max_tokens=int(limits.get("default_max_tokens", 8000)),
        escalated_max_tokens=int(limits.get("escalated_max_tokens", 16000)),
        context_limit=int(limits.get("context_limit", 50000)),
        keep_recent_tool_results=int(limits.get("keep_recent_tool_results", 3)),
        persist_threshold=int(limits.get("persist_threshold", 30000)),
        max_retries=int(runtime.get("max_retries", 3)),
        max_consecutive_529=int(runtime.get("max_consecutive_529", 2)),
        max_recovery_retries=int(runtime.get("max_recovery_retries", 2)),
        base_delay_ms=int(runtime.get("base_delay_ms", 500)),
        prompt=str(runtime.get("prompt", "\033[36magent >> \033[0m")),
        mode=mode,
        os_name=platform.system(),
        shell_name=_detect_shell_name(),
        web_search=WebSearchSettings(
            provider=search_provider,
            timeout_seconds=search_timeout,
            max_results=search_max_results,
        ),
    )
