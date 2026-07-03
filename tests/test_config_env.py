from pathlib import Path

from codeagent.core import config as config_module


SEARCH_ENV_NAMES = [
    "CODEAGENT_WEB_SEARCH_PROVIDER",
    "WEB_SEARCH_PROVIDER",
    "CODEAGENT_WEB_SEARCH_TIMEOUT_SECONDS",
    "WEB_SEARCH_TIMEOUT_SECONDS",
    "CODEAGENT_WEB_SEARCH_MAX_RESULTS",
    "WEB_SEARCH_MAX_RESULTS",
    "BRAVE_SEARCH_API_KEY",
    "TAVILY_API_KEY",
    "SERPAPI_API_KEY",
    "BING_SEARCH_API_KEY",
]


def _prepare_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_module, "load_dotenv", lambda override=True: None)
    for name in SEARCH_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_env_api_key_auto_selects_provider_without_config(monkeypatch, tmp_path):
    _prepare_env(monkeypatch, tmp_path)
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

    settings = config_module.load_settings()

    assert settings.web_search.provider == "brave"


def test_config_example_is_not_loaded(monkeypatch, tmp_path):
    _prepare_env(monkeypatch, tmp_path)
    (tmp_path / "config.example.yaml").write_text(
        "web_search:\n  provider: disabled\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")

    settings = config_module.load_settings()

    assert settings.web_search.provider == "brave"


def test_explicit_env_provider_and_limits_win(monkeypatch, tmp_path):
    _prepare_env(monkeypatch, tmp_path)
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-key")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("WEB_SEARCH_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("WEB_SEARCH_MAX_RESULTS", "3")

    settings = config_module.load_settings()

    assert settings.web_search.provider == "tavily"
    assert settings.web_search.timeout_seconds == 7
    assert settings.web_search.max_results == 3
