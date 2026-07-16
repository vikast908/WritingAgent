"""Provider registry - every model host the agent can talk to.

The whole pipeline speaks ONE wire format: OpenAI chat-completions (text and
JSON-mode structured output). Every host below is OpenAI-compatible, directly or
via a compat endpoint, so there is exactly one transport and adding a provider is
a single entry in `_PROVIDERS` - no code changes anywhere else.

Switch providers via `/provider <id>` in the shell, the `provider` setting, or
the WRITINGAGENT_PROVIDER env var. Each provider reads its key from its own env var
(OPENROUTER_API_KEY, DEEPSEEK_API_KEY, ...) and its base URL can be overridden by
the matching *_BASE_URL var (for proxies / self-hosted gateways).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    id: str                                   # canonical id, e.g. "deepseek"
    name: str                                 # display name, e.g. "DeepSeek"
    base_url: str                             # OpenAI-compatible endpoint
    key_env: tuple[str, ...]                  # env vars checked in order for the key
    base_url_env: str = ""                    # optional env var to override base_url
    reports_cost: bool = False                # returns usage.cost (OpenRouter does)
    headers: tuple[tuple[str, str], ...] = () # extra default headers
    local: bool = False                       # local server - no API key required
    notes: str = ""                           # one-line hint shown in /provider


# The registry. Grouped loosely by kind; all share the OpenAI chat transport.
_PROVIDERS = [
    # ── aggregators ──────────────────────────────────────────────────────────
    Provider("openrouter", "OpenRouter", "https://openrouter.ai/api/v1",
             ("OPENROUTER_API_KEY",), "OPENROUTER_BASE_URL", reports_cost=True,
             headers=(("X-Title", "Writing Agent"),),
             notes="aggregator - 300+ models, reports real USD cost (default)"),
    Provider("together", "Together AI", "https://api.together.xyz/v1",
             ("TOGETHER_API_KEY",), "TOGETHER_BASE_URL", notes="open-weights aggregator"),
    Provider("fireworks", "Fireworks AI", "https://api.fireworks.ai/inference/v1",
             ("FIREWORKS_API_KEY",), "FIREWORKS_BASE_URL", notes="open-weights aggregator"),
    Provider("deepinfra", "DeepInfra", "https://api.deepinfra.com/v1/openai",
             ("DEEPINFRA_API_KEY",), "DEEPINFRA_BASE_URL", notes="open-weights aggregator"),
    # ── first-party APIs ─────────────────────────────────────────────────────
    Provider("deepseek", "DeepSeek", "https://api.deepseek.com/v1",
             ("DEEPSEEK_API_KEY",), "DEEPSEEK_BASE_URL",
             notes="direct - deepseek-chat, deepseek-reasoner"),
    Provider("openai", "OpenAI", "https://api.openai.com/v1",
             ("OPENAI_API_KEY",), "OPENAI_BASE_URL", notes="gpt-* via chat completions"),
    Provider("anthropic", "Anthropic Claude", "https://api.anthropic.com/v1",
             ("ANTHROPIC_API_KEY",), "ANTHROPIC_BASE_URL",
             notes="claude-* via Anthropic's OpenAI-compatible endpoint (bare slugs, "
                   "e.g. claude-sonnet-4); for full structured-output support route via OpenRouter"),
    Provider("google", "Google Gemini",
             "https://generativelanguage.googleapis.com/v1beta/openai",
             ("GEMINI_API_KEY", "GOOGLE_API_KEY"), "GOOGLE_BASE_URL",
             notes="gemini-* via the OpenAI-compatible endpoint"),
    Provider("xai", "xAI Grok", "https://api.x.ai/v1",
             ("XAI_API_KEY",), "XAI_BASE_URL", notes="grok-* via chat completions"),
    Provider("groq", "Groq", "https://api.groq.com/openai/v1",
             ("GROQ_API_KEY",), "GROQ_BASE_URL", notes="fast inference, open-weights"),
    Provider("cerebras", "Cerebras", "https://api.cerebras.ai/v1",
             ("CEREBRAS_API_KEY",), "CEREBRAS_BASE_URL", notes="very fast open-weights inference"),
    Provider("sambanova", "SambaNova", "https://api.sambanova.ai/v1",
             ("SAMBANOVA_API_KEY",), "SAMBANOVA_BASE_URL", notes="fast open-weights inference"),
    Provider("perplexity", "Perplexity", "https://api.perplexity.ai",
             ("PERPLEXITY_API_KEY",), "PERPLEXITY_BASE_URL",
             notes="sonar* - answers with live web citations"),
    Provider("mistral", "Mistral", "https://api.mistral.ai/v1",
             ("MISTRAL_API_KEY",), "MISTRAL_BASE_URL"),
    Provider("moonshot", "Moonshot / Kimi", "https://api.moonshot.ai/v1",
             ("MOONSHOT_API_KEY",), "MOONSHOT_BASE_URL"),
    Provider("dashscope", "Qwen / DashScope",
             "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
             ("DASHSCOPE_API_KEY", "QWEN_API_KEY"), "DASHSCOPE_BASE_URL"),
    Provider("zhipu", "Zhipu GLM", "https://open.bigmodel.cn/api/paas/v4",
             ("ZHIPU_API_KEY",), "ZHIPU_BASE_URL"),
    Provider("nvidia", "NVIDIA NIM", "https://integrate.api.nvidia.com/v1",
             ("NVIDIA_API_KEY",), "NVIDIA_BASE_URL"),
    # ── local servers (no key needed) ────────────────────────────────────────
    Provider("ollama", "Ollama (local)", "http://127.0.0.1:11434/v1",
             (), "OLLAMA_BASE_URL", local=True,
             notes="local models - run `ollama serve` first"),
    Provider("lmstudio", "LM Studio (local)", "http://127.0.0.1:1234/v1",
             (), "LMSTUDIO_BASE_URL", local=True,
             notes="local models - start the LM Studio server"),
    # ── enterprise / gateway-fronted (need an OpenAI-compatible gateway URL) ───
    # AWS Bedrock and Azure OpenAI are NOT plain OpenAI-compatible base-URL swaps
    # (Bedrock uses SigV4/boto3; Azure needs api-version + a deployment). The whole
    # pipeline speaks one wire format, so both are reached through an OpenAI-compatible
    # gateway you point the *_BASE_URL var at - e.g. a LiteLLM proxy, or AWS's own
    # `bedrock-access-gateway`. The gateway holds the cloud credentials; the key here is
    # the gateway's key. (A native boto3 Bedrock transport is a roadmap item, see ROADMAP.md.)
    Provider("bedrock", "AWS Bedrock (via gateway)", "",
             ("AWS_BEDROCK_API_KEY", "BEDROCK_API_KEY"), "AWS_BEDROCK_BASE_URL",
             notes="set AWS_BEDROCK_BASE_URL to an OpenAI-compatible Bedrock gateway "
                   "(LiteLLM / bedrock-access-gateway); model = the gateway's slug"),
    Provider("azure", "Azure OpenAI (via gateway)", "",
             ("AZURE_OPENAI_API_KEY", "AZURE_API_KEY"), "AZURE_OPENAI_BASE_URL",
             notes="set AZURE_OPENAI_BASE_URL to an OpenAI-compatible Azure gateway/proxy; "
                   "model = your deployment name"),
    # ── escape hatch ─────────────────────────────────────────────────────────
    Provider("custom", "Custom endpoint", "",
             ("WRITINGAGENT_API_KEY", "OPENAI_API_KEY"), "WRITINGAGENT_BASE_URL",
             notes="point WRITINGAGENT_BASE_URL at any OpenAI-compatible server"),
]

REGISTRY: dict[str, Provider] = {p.id: p for p in _PROVIDERS}

# Type whatever's shortest; resolves to a canonical id.
ALIASES = {
    "or": "openrouter", "router": "openrouter",
    "ds": "deepseek",
    "gpt": "openai", "oai": "openai", "chatgpt": "openai",
    "claude": "anthropic", "anthropicai": "anthropic",
    "gemini": "google", "googleai": "google",
    "grok": "xai",
    "kimi": "moonshot", "moonshotai": "moonshot",
    "qwen": "dashscope", "alibaba": "dashscope", "aliyun": "dashscope",
    "glm": "zhipu", "zhipuai": "zhipu", "zai": "zhipu", "bigmodel": "zhipu",
    "nim": "nvidia",
    "pplx": "perplexity", "sonar": "perplexity",
    "aws": "bedrock", "amazon": "bedrock",
    "azureopenai": "azure", "aoai": "azure",
    "local": "ollama", "lm-studio": "lmstudio", "lms": "lmstudio",
}

# No blessed default: the writer chooses a host (first-run wizard, `/provider`, the `provider`
# setting, or WRITINGAGENT_PROVIDER). This value is only the last-resort seed when nothing is
# configured and no provider key is auto-detected - OpenRouter because it fronts every vendor
# below with one key and reports real USD cost, so a brand-new user has the widest reach.
DEFAULT = "openrouter"


def resolve(name: str) -> str:
    """Canonical id for a user-typed provider name/alias (lowercased)."""
    n = (name or "").strip().lower()
    return ALIASES.get(n, n)


def get(name: str) -> Provider | None:
    """Provider for a name/alias, or None if unknown."""
    return REGISTRY.get(resolve(name))


def base_url_for(p: Provider) -> str:
    """Effective base URL - the *_BASE_URL override env wins over the default."""
    if p.base_url_env:
        return os.getenv(p.base_url_env, p.base_url)
    return p.base_url


def api_key_for(p: Provider) -> str | None:
    """First non-empty key from the provider's env vars, or None."""
    for env in p.key_env:
        val = os.getenv(env)
        if val:
            return val
    return None


def has_credentials(p: Provider) -> bool:
    """True if this provider is usable right now (local, or a key is present)."""
    return p.local or api_key_for(p) is not None


def names() -> list[str]:
    """All canonical provider ids, in registry order."""
    return [p.id for p in _PROVIDERS]


def configured() -> list[Provider]:
    """Providers usable RIGHT NOW - a key is present in the environment. Excludes local
    servers (always "usable" but not proof of intent) and gateway/custom entries (their key
    env doubles as another provider's). Drives the no-default first-run picker: if the writer
    has exactly one key set we use it; if several, we ask; if none, we offer the full menu."""
    gateways = {"custom", "bedrock", "azure"}
    return [p for p in _PROVIDERS
            if p.id not in gateways and not p.local and api_key_for(p) is not None]


# A small, curated catalog of popular models for discovery (`/model list` and slug
# completion). These are OpenRouter slugs (vendor/model) - the default host; on a
# first-party host (see /provider) use that host's own bare slug. NOT exhaustive -
# ANY slug works with /model; browse the full list at openrouter.ai/models.
POPULAR_MODELS: list[tuple[str, tuple[str, ...]]] = [
    ("DeepSeek",  ("deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash",
                   "deepseek/deepseek-r1", "deepseek/deepseek-chat")),
    ("Anthropic", ("anthropic/claude-opus-4", "anthropic/claude-sonnet-4",
                   "anthropic/claude-3.5-haiku")),
    ("OpenAI",    ("openai/gpt-4o", "openai/gpt-4o-mini", "openai/o1")),
    ("Google",    ("google/gemini-2.5-pro", "google/gemini-2.5-flash")),
    ("Meta",      ("meta-llama/llama-3.3-70b-instruct",)),
    ("xAI",       ("x-ai/grok-2",)),
    ("Qwen",      ("qwen/qwen-2.5-72b-instruct",)),
    ("Mistral",   ("mistralai/mistral-large",)),
    ("Perplexity", ("perplexity/sonar", "perplexity/sonar-pro")),
]


def model_slugs() -> list[str]:
    """Flat list of the curated popular model slugs (for completion)."""
    return [s for _fam, slugs in POPULAR_MODELS for s in slugs]
