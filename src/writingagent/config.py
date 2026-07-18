"""Model routing (models.yaml) and engine settings (settings.yaml), from <home>/config/."""
from __future__ import annotations

import dataclasses
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import paths

# User-editable config lives in the agent home (see paths.py), never the install tree.
_MODELS = paths.HOME / "config" / "models.yaml"
_SETTINGS = paths.HOME / "config" / "settings.yaml"
# Defaults bundled inside the wheel. models.yaml is copied out to _MODELS on first
# load so /model edits land in a real, user-editable file.
_BUNDLED = Path(__file__).resolve().parent / "resources"


class ModelConfig:
    """Resolves which model and sampling temperature to use for each node."""

    def __init__(self, data: dict):
        # Matches the shipped config/models.yaml default and the plan's DeepSeek-only
        # routing (§12.1). Only used when models.yaml is absent; an Anthropic slug here
        # would silently route every node to a model no configured provider serves.
        self._default = data.get("default", "deepseek/deepseek-v4-pro")
        self._nodes = data.get("nodes", {}) or {}
        self._temperature = data.get("temperature", {}) or {}
        self._max_tokens = data.get("max_tokens", {}) or {}   # per-node completion caps
        # Per-node repetition penalties (A-024). A mild positive frequency_penalty on the
        # writer directly attacks the token-level repetition the humanizer cleans up after
        # the fact. Both are clamped to OpenAI's [-2, 2] in the getters. Empty = unset.
        self._frequency_penalty = data.get("frequency_penalty", {}) or {}
        self._presence_penalty = data.get("presence_penalty", {}) or {}
        # The cheapest reliable model to retry on after the primary exhausts its retries
        # (plan §12.1 fallback). Empty = no fallback. One global slug, not per-node.
        self._fallback = data.get("fallback", "")

    def resolved_for(self, node: str) -> str:
        """The model slug routed for `node`, WITHOUT model_for's telemetry side effect.
        Use this for routing DECISIONS (e.g. cost-mode setup) that must not re-tag the
        telemetry thread with a node whose LLM call hasn't happened yet."""
        return self._nodes.get(node, self._default)

    def model_for(self, node: str) -> str:
        # Every call site resolves its model via model_for(<node>) immediately before
        # the LLM call, so this is the one seam that knows which AGENT a call belongs
        # to - tag the thread so telemetry can attribute cost per node (web dashboard).
        try:
            from . import llm
            llm.set_node(node)
        except Exception:  # noqa: BLE001 - attribution must never break routing
            pass
        return self.resolved_for(node)

    def temperature_for(self, node: str):
        """May be None. The LLM wrapper drops it for models that reject sampling."""
        return self._temperature.get(node)

    @staticmethod
    def _clamp_penalty(v):
        """Clamp a penalty to OpenAI's accepted [-2, 2]; None/garbage -> None (unset)."""
        try:
            return min(2.0, max(-2.0, float(v)))
        except (TypeError, ValueError):
            return None

    def frequency_penalty_for(self, node: str):
        """Per-node frequency_penalty (None when unset). The LLM wrapper omits it if None."""
        return self._clamp_penalty(self._frequency_penalty.get(node))

    def presence_penalty_for(self, node: str):
        """Per-node presence_penalty (None when unset). The LLM wrapper omits it if None."""
        return self._clamp_penalty(self._presence_penalty.get(node))

    def max_tokens_for(self, node: str, default: int) -> int:
        """Per-node completion cap from models.yaml `max_tokens:` (falls back to the
        caller's default). Bounds reasoning runaway / truncation-retries on short nodes
        without risking the long-form writer, which keeps its generous default."""
        try:
            return int(self._max_tokens.get(node, default))
        except (TypeError, ValueError):
            return default

    @property
    def default(self) -> str:
        return self._default

    @property
    def fallback(self) -> str:
        """Global fallback model slug (e.g. a flash tier) tried once after the primary
        model exhausts its retries on a node. Empty string = no fallback (plan §12.1)."""
        return self._fallback

    def set_default(self, model: str) -> None:
        self._default = model

    def set_node(self, node: str, model: str) -> None:
        self._nodes[node] = model

    def set_all(self, model: str) -> None:
        """Route every agent to one model (clears per-node overrides)."""
        self._default = model
        self._nodes = {}

    def to_dict(self) -> dict:
        return {"default": self._default, "nodes": dict(self._nodes),
                "temperature": dict(self._temperature), "max_tokens": dict(self._max_tokens),
                "frequency_penalty": dict(self._frequency_penalty),
                "presence_penalty": dict(self._presence_penalty),
                "fallback": self._fallback}


@dataclass
class Settings:
    default_user: str = "default"
    num_chapters: int = 8
    max_revisions: int = 2
    consolidate_every: int = 5
    use_researcher: bool = True              # web grounding per unit - off means citations are unverifiable
    search_provider: str = "duckduckgo"      # web search backend: duckduckgo (free, default) | firecrawl |
    #                                          tavily | brave | serpapi | exa | parallel. Keyed providers read
    #                                          their key from env (see .env.example); a missing key or any
    #                                          error degrades to duckduckgo (search never blocks a run).
    #                                          firecrawl additionally switches deep-research scraping to Firecrawl.
    deep_research: bool = False               # multi-source fetch+synthesize (needs use_researcher; plan §15)
    divergent_drafts: int = 2                # first-attempt drafts at varied temps; critic picks best (1 = off)
    divergent_skeletons: bool = False        # draft the N variants SHORT (skeleton), judge, expand only the winner
    #                                          to full length - cuts discarded completion tokens ~60%. Opt-in: a
    #                                          short skeleton reveals less about the full draft, so off by default.
    tournament_judge: bool = True            # pick the best divergent draft side-by-side, not by scalar self-score
    min_insight: int = 3                     # critic insight (1-5) required to approve (0 = off)
    skill_duels: bool = False                # A/B-test learned skills: draft one extra variant with a candidate
    #                                          skill held out and let the critic say if it helped - a true
    #                                          counterfactual (the causal efficacy signal). Opt-in: costs one
    #                                          extra draft on units that still have undecided skills.
    learn_preferences: bool = True           # accumulate the user's review/revise corrections into a durable
    #                                          cross-run preferences file; the learner distills them into skills +
    #                                          watch items so the agent follows the user's tastes on the next run.
    skill_distill: bool = False              # after learning, retire near-duplicate skills (keep the best-scoring
    #                                          one) so retrieval stays sharp. Safe only once duels give real
    #                                          scores, so off by default. Non-destructive (sets status only).
    watch_blocking: bool = True              # watch-list violations: True = block only CLEAR, CONCRETE ones
    #                                          (borderline/stylistic -> nit); False = fully advisory (nit only).
    verify_claims: bool = True               # check each [N]-cited claim against its source; unsupported = blocking
    verify_excerpt_chars: int = 6000         # per-source chars the claim VERIFIER reads (the full deep-research
    #                                          fetch). Must cover the whole fetched page: verifying against the
    #                                          shorter synthesis excerpt flags true claims whose support sits
    #                                          past the cut as fabrication - and that BLOCKS. 0 = no cap.
    table_read: bool = True                  # whole-article cold read by a skeptical reader (report only)
    seo_keyword: str = ""                    # primary keyword to target FROM THE START: threaded into the
    #                                          writer/critic so the piece is written for it (title, opening,
    #                                          headings), and applied post-validation. "" = infer after.
    auto_promote: bool = True                # after a finished `write`: apply SEO + run the audit + promo pack
    #                                          automatically (plan §24). LOCAL artifacts only - a report,
    #                                          keywords.json, and promo/*.md drafts; it never modifies the
    #                                          manuscript and never posts anything anywhere.
    table_read_revise: bool = False          # autonomous: apply the reader's single top fix as one bounded revision
    escalate_below_confidence: float = 0.5   # critic confidence below this -> escalate (plan §7)
    escalate_on_contradiction: bool = True   # consolidation contradictions -> review (plan §9)
    autonomous: bool = True                  # no human-in-the-loop: never pause, commit best draft
    humanize: bool = True                    # rewrite each chapter to strip AI tells (em-dashes...)
    article_cohesion: bool = True            # whole-article smoothing pass before References
    book_cohesion: bool = True               # book: deterministic cross-chapter repetition report
    #                                          after assembly (detector, not a rewriter - a full
    #                                          10-chapter rewrite is impractical/lossy; D-008)
    use_images: bool = True                  # include images at all (non-fiction/illustrated); off = no figures
    image_source: str = "openverse,wikimedia"  # ordered comma list of free-licensed sources to try, first hit
    #                                          wins: openverse, wikimedia (keyless), pixabay, pexels, unsplash
    #                                          (keyed), generate (a text-to-image model). Falls back to an SVG
    #                                          diagram if none produce. See images.image_sources().
    image_model: str = ""                    # image-gen model slug (e.g. gpt-image-1, dall-e-3, an OpenRouter
    #                                          image model). "" disables generation even if image_source=generate.
    image_provider: str = ""                 # host that serves image generation ("" = the main `provider`), so
    #                                          chat can run on one host and image-gen on another (any OpenAI-compatible)
    diagram_engine: str = "auto"             # diagram renderer: auto (= builtin) | d2 (explicit opt-in, D2+ELK) | builtin
    use_embeddings: bool = False             # semantic skill retrieval (requires sentence-transformers)
    request_timeout: float = 60.0           # per-LLM-request network timeout (seconds)
    max_run_tokens: int = 0                 # HARD ceiling: pause a run once total tokens exceed this (0 =
    #                                         unlimited / let budget mode auto-scale). An explicit value wins.
    budget_tokens_per_unit: int = 20000     # budget mode: session budget scales as ~this * unit_count + overhead
    #                                         so a full article FINISHES rather than pausing mid-way (tunable)
    cost_mode: str = "standard"             # "standard" = current behavior | "budget" = pin the spend-heavy
    #                                         knobs lean (1 draft, 1 revision, no table read, 12k context,
    #                                         100k hard token cap) and route the judgment nodes (critic/judge/
    #                                         verifier/consolidation/diagram) to the flash tier - targets
    #                                         <=100k tokens per article. Every pin is an existing tunable;
    #                                         apply_cost_mode() is the single place the profile lives.
    max_context_chars: int = 24000          # budget for the assembled canon+summaries+excerpts block
    #                                         (drops lowest-priority parts first); guards against blowing
    #                                         the model window on long books. 0 = unbounded.
    mode: str = "article"        # "book" | "article" - default for new projects
    num_sections: int = 6        # default section count for articles
    theme: str = "editorial"     # TUI color theme (see ui.THEMES; /theme to switch)
    provider: str = "openrouter" # model host (see providers.py; /provider to switch)
    openrouter_providers: str = ""  # comma-separated OpenRouter upstreams to pin (e.g. "DeepSeek") so
    #                                 DeepSeek's prompt cache engages; "" = OpenRouter default routing.
    #                                 Budget mode auto-pins this for a DeepSeek default (see apply_cost_mode);
    #                                 setting it explicitly engages the cache in standard mode too.
    export_dir: str = ""         # default save folder for exports ("" = each project's own folder; /path)
    strip_inline_citations: bool = True   # remove [N] markers from prose; sourcing lives only in end References
    rank_references: bool = True          # final References scored by influence (0-100), dated, sorted high->low
    # ── Register / genre craft layer (plan §22) ──
    register: str = ""           # "" = infer from genre/angle; else pin one (registers.names(): nonfiction,
    #                              technical, literary-fiction, genre-fiction, academic, journalism,
    #                              copywriting, business, poetry, screenplay, children)
    field: str = ""              # "" = the register's default structure; else pin a field template
    #                              (fields.names(): inverted-pyramid, imrad, aida, bluf, how-to, three-act, ...)
    citation_style: str = ""     # "" = register default; else influence|numeric|apa|mla|chicago|ap|none
    craft_passes: bool = True    # run surgical show-don't-tell / de-passive on each committed unit (plan §22)
    # ── Compositor manner layers (plan §23) ──
    persona: str = ""            # "" = none; else a voice (personas.names(): wry-skeptic, warm-mentor,
    #                              hard-boiled-minimalist, lyrical-maximalist, deadpan-technical,
    #                              firebrand-essayist, shakespearean, nietzschean, austen-ironic,
    #                              twain-vernacular). Dropped if it doesn't fit the register.
    emotion: str = ""            # "" = none; else a per-run emotional target (emotions.names(): fear,
    #                              anger, grief, joy, love, shame, tension, hope) - show-don't-name cue
    # ── Agentic controller (plan §21) - opt-in self-directing loop over the fixed pipeline ──
    agentic: bool = False                 # drive units through the controller (choose research/canon then draft)
    #                                       instead of the fixed pipeline. Default OFF => today's behavior, no risk.
    agentic_policy: str = "default"       # who chooses the next action: default (always draft, == fixed pipeline) |
    #                                       llm (a ReAct controller call) | trace (Phase-5 learned-policy seam)
    agentic_controller_model: str = "judge"  # per-node routing key for the llm policy's model (cheap/light reasoning)
    agentic_max_unit_steps: int = 3       # max research/read_canon gathering steps before a unit must be drafted
    agentic_factcheck_panel: bool = False  # multi-agent fact-check panel utility (plan §21.10; majority-vote verify)
    agentic_inline_tools: bool = False    # let the WRITER call research/read_canon mid-draft (in-generation
    #                                       tool use, plan §21 Phase 3). Off by default: needs a tool-calling
    #                                       provider and costs extra round-trips; agentic runs only.
    agentic_critique_panel: bool = False  # diverse-lens majority critique before approving a section
    #                                       (plan §21.10; articles; agentic runs only)


# ── Cost modes (plan §19) ─────────────────────────────────────────────────────
# The budget profile's pins. All tunable constants live here, not scattered in the
# orchestrator; "standard" mode never touches any of them.
BUDGET_FLASH_NODES = ("critic", "judge", "verifier", "consolidation", "diagram")
BUDGET_MAX_CONTEXT_CHARS = 12_000
# The run token budget scales with unit count (so a full article FINISHES instead of
# pausing mid-way, the "cap not working" complaint), unless the user pins an explicit
# max_run_tokens (a hard ceiling that always wins). ~20k/unit + fixed overhead for the
# thesis/outline/produce/seo/promote/learn tail (and the agentic controller's extra calls,
# measured ~40k on a real agentic run - hence the headroom). Both tunable.
BUDGET_OVERHEAD_TOKENS = 35_000


def budget_for_units(settings: Settings, units: int) -> int:
    """The session token budget for a run (0 = unlimited).

    An explicit `max_run_tokens` (>0) is a HARD ceiling and always wins. Otherwise
    budget mode auto-scales by unit count so the whole piece completes; standard mode
    with no cap is unlimited (historical behavior)."""
    if getattr(settings, "max_run_tokens", 0) and settings.max_run_tokens > 0:
        return settings.max_run_tokens
    if getattr(settings, "cost_mode", "standard") == "budget":
        per = getattr(settings, "budget_tokens_per_unit", 20_000) or 20_000
        return BUDGET_OVERHEAD_TOKENS + max(1, int(units or 1)) * per
    return 0


def apply_cost_mode(cfg: ModelConfig, settings: Settings):
    """Apply the cost profile: returns (cfg, settings, notes).

    `budget` returns ADJUSTED COPIES (the caller's objects are untouched) with the
    spend-heavy knobs pinned lean and the judgment nodes routed to the global fallback
    (flash) tier; `notes` lists what was pinned, for the run log. Any other mode
    returns the inputs unchanged. The profile only ever *tightens* a knob - a user
    value already leaner than the pin is kept."""
    if getattr(settings, "cost_mode", "standard") != "budget":
        return cfg, settings, []
    notes: list[str] = []
    s = dataclasses.replace(settings)
    if s.divergent_drafts > 1:
        s.divergent_drafts = 1
        notes.append("divergent_drafts=1")
    if s.max_revisions > 1:
        s.max_revisions = 1
        notes.append("max_revisions=1")
    if s.table_read or s.table_read_revise:
        s.table_read = False
        s.table_read_revise = False
        notes.append("table_read=off")
    if s.max_context_chars == 0 or s.max_context_chars > BUDGET_MAX_CONTEXT_CHARS:
        s.max_context_chars = BUDGET_MAX_CONTEXT_CHARS
        notes.append(f"max_context_chars={BUDGET_MAX_CONTEXT_CHARS}")
    # NOTE: the run token budget is no longer pinned here to a flat value - it is computed
    # per-run by budget_for_units() (scales with unit count) so a full piece finishes.
    flash = cfg.fallback
    if flash:
        cfg2 = ModelConfig(cfg.to_dict())
        for node in BUDGET_FLASH_NODES:
            if cfg.resolved_for(node) != flash:
                cfg2.set_node(node, flash)
                notes.append(f"{node}->{flash.rsplit('/', 1)[-1]}")
        cfg = cfg2
    # Engage the provider's prompt cache. Prompt tokens are ~65% of a run's spend (measured),
    # but on OpenRouter DeepSeek's automatic context cache only fires when the upstream is
    # pinned - an unpinned run was seen caching just 10% of its prompt tokens, paying full
    # price on the dominant cost. If the default model is a DeepSeek slug and nothing is
    # pinned, pin it (fallbacks stay on): a large, safe efficiency win. No-op off OpenRouter
    # or for a non-DeepSeek default; a user's own pin is always respected.
    if not (getattr(s, "openrouter_providers", "") or "").strip():
        vendor = cfg.default.split("/", 1)[0].strip().lower() if "/" in cfg.default else ""
        if vendor == "deepseek":
            s.openrouter_providers = "DeepSeek"
            notes.append("cache-pin=DeepSeek")
    return cfg, s, notes


def load_config() -> ModelConfig:
    if not _MODELS.exists():
        bundled = _BUNDLED / "models.yaml"
        if not bundled.exists():
            return ModelConfig({})   # sensible defaults; mirrors load_settings' guard
        try:
            _MODELS.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundled, _MODELS)
        except OSError:
            # Read-only install dir etc.: still serve the bundled routing (incl. the
            # fallback model) read-only rather than degrading to bare defaults.
            with open(bundled, encoding="utf-8") as f:
                return ModelConfig(yaml.safe_load(f) or {})
    with open(_MODELS, encoding="utf-8") as f:
        return ModelConfig(yaml.safe_load(f) or {})


def save_config(cfg: ModelConfig) -> None:
    """Persist model routing back to config/models.yaml (e.g. after a /model change)."""
    data = cfg.to_dict()
    lines = ["# Per-node model routing (OpenRouter slugs). Edit here or via the shell /model command.",
             f"default: {data['default']}"]
    if data.get("fallback"):
        lines.append(f"fallback: {data['fallback']}   # retried once after the primary fails")
    lines += ["", "nodes:"]
    lines += [f"  {k}: {v}" for k, v in data["nodes"].items()]
    if data["temperature"]:
        lines += ["", "temperature:"]
        lines += [f"  {k}: {v}" for k, v in data["temperature"].items()]
    if data.get("max_tokens"):
        lines += ["", "max_tokens:"]
        lines += [f"  {k}: {v}" for k, v in data["max_tokens"].items()]
    if data.get("frequency_penalty"):
        lines += ["", "frequency_penalty:"]
        lines += [f"  {k}: {v}" for k, v in data["frequency_penalty"].items()]
    if data.get("presence_penalty"):
        lines += ["", "presence_penalty:"]
        lines += [f"  {k}: {v}" for k, v in data["presence_penalty"].items()]
    _MODELS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clamp_settings(s: Settings) -> Settings:
    """Clamp out-of-range values to sane bounds so a typo in settings.yaml can't produce
    baffling runtime behavior (e.g. min_insight: 99 makes every unit fail the gate forever,
    a negative max_revisions breaks the loop range). Clamps in place and returns `s` -
    never raises, so a run degrades rather than refusing to start."""
    # default_user is a filesystem-safe id; a bad value (e.g. YAML-parsed as an int, or an
    # unsafe string) heals to "default" instead of crashing everything that uses the uid.
    from . import brain
    if not brain.is_safe_id(s.default_user):
        s.default_user = "default"
    s.num_chapters = max(1, s.num_chapters)
    s.num_sections = max(1, s.num_sections)
    s.max_revisions = max(0, s.max_revisions)
    s.consolidate_every = max(1, s.consolidate_every)
    s.divergent_drafts = max(1, s.divergent_drafts)
    s.min_insight = min(5, max(0, s.min_insight))            # 0 = off; the scale is 1-5
    s.escalate_below_confidence = min(1.0, max(0.0, s.escalate_below_confidence))
    s.request_timeout = s.request_timeout if s.request_timeout > 0 else 60.0
    s.max_run_tokens = max(0, s.max_run_tokens)              # 0 = unlimited
    s.budget_tokens_per_unit = max(1000, s.budget_tokens_per_unit)  # a sane per-unit floor
    s.verify_excerpt_chars = max(0, s.verify_excerpt_chars)  # 0 = no cap
    s.max_context_chars = max(0, s.max_context_chars)        # 0 = unbounded
    s.agentic_max_unit_steps = max(0, s.agentic_max_unit_steps)
    if s.mode not in ("book", "article"):
        s.mode = "article"
    if s.cost_mode not in ("standard", "budget"):
        s.cost_mode = "standard"
    try:
        from . import search as _search
        _providers = _search.PROVIDERS
    except Exception:  # noqa: BLE001 - never let a validation import break load_settings
        _providers = ("duckduckgo", "firecrawl", "tavily", "brave", "serpapi", "exa", "parallel")
    if s.search_provider not in _providers:
        s.search_provider = "duckduckgo"
    # image_source is an ordered comma list of known sources; drop unknown tokens and
    # fall back to the keyless default if nothing valid remains. Lazy import (no cycle:
    # images doesn't import config at module scope).
    try:
        from . import images as _images
        _srcs = _images.parse_sources(s.image_source)
        s.image_source = ",".join(_srcs) if _srcs else "openverse,wikimedia"
    except Exception:  # noqa: BLE001 - never let this validation break load_settings
        if not s.image_source:
            s.image_source = "openverse,wikimedia"
    if s.agentic_policy not in ("default", "llm", "trace"):
        s.agentic_policy = "default"
    # Register / field / citation-style: validate against the known sets; an unknown value
    # falls back to "" (= infer / register default) so a typo degrades, never crashes a run.
    # Lazy import keeps config free of an import cycle (registers/fields don't import config).
    from . import fields as _fields
    from . import registers as _registers
    # "random" is a valid sentinel for every voice field - resolved to a concrete choice
    # once at project creation (resolve_random), so the setting can carry it through here.
    if s.register:
        norm = s.register.strip().lower().replace("_", "-")
        s.register = norm if (norm == "random" or norm in _registers.names()) else ""
    if s.field:
        norm = s.field.strip().lower()
        s.field = norm if (norm == "random" or norm in _fields.names()) else ""
    if s.citation_style:
        norm = s.citation_style.strip().lower()
        s.citation_style = norm if norm in (
            "random", "influence", "numeric", "apa", "mla", "chicago", "ap", "none") else ""
    # Persona / emotion (compositor manner layers, plan §23): validate against the known
    # sets (emotion tolerates aliases via emotions.get); unknown -> "" (= none).
    from . import emotions as _emotions
    from . import personas as _personas
    if s.persona:
        norm = s.persona.strip().lower().replace("_", "-")
        s.persona = norm if (norm == "random" or norm in _personas.names()) else ""
    if s.emotion:
        norm = s.emotion.strip().lower()
        s.emotion = norm if (norm == "random" or _emotions.get(s.emotion)) else ""
    return s


def resolve_random(settings: Settings) -> Settings:
    """Replace any voice field set to "random" with a concrete random pick from its set,
    so each NEW project gets a specific choice - consistent within the piece, varied across
    pieces. Returns a copy (the caller's object is untouched); non-random values pass through.
    Called once at project creation, before the pipeline reads register/field/persona/etc."""
    import random

    from . import emotions as _emotions
    from . import fields as _fields
    from . import personas as _personas
    from . import registers as _registers
    s = dataclasses.replace(settings)
    pools = {
        "register": list(_registers.names()),
        "field": list(_fields.names()),
        "persona": list(_personas.names()),
        "emotion": list(_emotions.names()),
        "citation_style": ["influence", "numeric", "apa", "mla", "chicago", "ap"],
    }
    for name, pool in pools.items():
        if (getattr(s, name, "") or "").strip().lower() == "random" and pool:
            setattr(s, name, random.choice(pool))
    return s


def load_settings() -> Settings:
    if _SETTINGS.exists():
        with open(_SETTINGS, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        valid = {f.name for f in dataclasses.fields(Settings)}
        return _clamp_settings(Settings(**{k: v for k, v in data.items() if k in valid}))
    return _clamp_settings(Settings())


def save_settings(s: Settings) -> None:
    """Persist Settings back to config/settings.yaml (e.g. after a /set command)."""
    lines = ["# Engine settings (tunable; see plan.md §15)."]
    for f in dataclasses.fields(s):
        v = getattr(s, f.name)
        if isinstance(v, bool):
            sval = str(v).lower()
        elif isinstance(v, str) and not v:
            # An empty string must round-trip as an empty string. Writing a bare
            # `key:` makes YAML load it back as None (e.g. export_dir -> Path("None")),
            # which silently corrupts the next save into the literal `key: None`.
            sval = '""'
        else:
            sval = v
        lines.append(f"{f.name}: {sval}")
    _SETTINGS.write_text("\n".join(lines) + "\n", encoding="utf-8")
