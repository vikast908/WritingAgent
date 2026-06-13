"""Multi-provider routing: the registry, alias/env resolution, and the llm wiring
that lets the agent point at any OpenAI-compatible host (OpenRouter by default)."""
import pytest

from book_agent import llm
from book_agent import providers as P


@pytest.fixture(autouse=True)
def _restore_default_provider():
    yield
    llm.configure_provider(P.DEFAULT)


def test_registry_has_default_and_locals():
    assert P.DEFAULT == "openrouter"
    assert P.get("openrouter").reports_cost          # only the aggregator reports cost
    assert not P.get("deepseek").reports_cost
    for local in ("ollama", "lmstudio"):
        p = P.get(local)
        assert p.local and P.has_credentials(p)       # local hosts are always usable


def test_aliases_resolve_to_canonical_ids():
    cases = {"grok": "xai", "ds": "deepseek", "kimi": "moonshot",
             "qwen": "dashscope", "glm": "zhipu", "local": "ollama", "gpt": "openai"}
    for alias, canonical in cases.items():
        assert P.resolve(alias) == canonical
        assert P.get(alias) is P.REGISTRY[canonical]
    assert P.get("does-not-exist") is None


def test_base_url_override_env_wins(monkeypatch):
    p = P.get("deepseek")
    assert P.base_url_for(p) == "https://api.deepseek.com/v1"
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://proxy.local/v1")
    assert P.base_url_for(p) == "http://proxy.local/v1"


def test_api_key_resolution_order(monkeypatch):
    p = P.get("google")                               # key_env = (GEMINI, GOOGLE)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "second")
    assert P.api_key_for(p) == "second"
    monkeypatch.setenv("GEMINI_API_KEY", "first")
    assert P.api_key_for(p) == "first"                # first non-empty in the tuple wins


def test_local_provider_needs_no_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    assert P.has_credentials(P.get("ollama")) is True
    assert P.has_credentials(P.get("custom")) in (True, False)  # depends on ambient env


def test_configure_provider_switches_and_gates_cost(monkeypatch):
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")
    llm.configure_provider("deepseek")
    assert llm.active_provider().id == "deepseek"
    assert llm._include_cost is False                 # non-aggregator: don't ask for cost
    llm.configure_provider("or")                      # alias
    assert llm.active_provider().id == "openrouter" and llm._include_cost is True


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="unknown provider"):
        llm.configure_provider("totally-made-up")


def test_client_builds_for_local_without_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    llm.configure_provider("ollama")
    llm._client = None
    client = llm._get_client()
    assert "11434" in str(client.base_url)            # local default endpoint


def test_missing_key_raises_clear_error(monkeypatch):
    for var in ("XAI_API_KEY", "XAI_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    llm.configure_provider("xai")
    llm._client = None
    with pytest.raises(RuntimeError, match="no API key for xAI Grok"):
        llm._get_client()


def test_fake_mode_unaffected_by_provider(monkeypatch):
    """Switching providers must never break the offline pipeline (fake bypasses the client)."""
    monkeypatch.setenv("BOOK_AGENT_FAKE", "1")
    llm.configure_provider("groq")
    assert "Placeholder" in llm.complete_text("any-model", "sys", "user")
