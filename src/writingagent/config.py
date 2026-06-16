"""Model routing (config/models.yaml) and engine settings (config/settings.yaml)."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_MODELS = _ROOT / "config" / "models.yaml"
_SETTINGS = _ROOT / "config" / "settings.yaml"


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

    def model_for(self, node: str) -> str:
        return self._nodes.get(node, self._default)

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
    skill_distill: bool = False              # after learning, retire near-duplicate skills (keep the best-scoring
    #                                          one) so retrieval stays sharp. Safe only once duels give real
    #                                          scores, so off by default. Non-destructive (sets status only).
    watch_blocking: bool = True              # watch-list violations: True = block only CLEAR, CONCRETE ones
    #                                          (borderline/stylistic -> nit); False = fully advisory (nit only).
    verify_claims: bool = True               # check each [N]-cited claim against its source; unsupported = blocking
    table_read: bool = True                  # whole-article cold read by a skeptical reader (report only)
    table_read_revise: bool = False          # autonomous: apply the reader's single top fix as one bounded revision
    escalate_below_confidence: float = 0.5   # critic confidence below this -> escalate (plan §7)
    escalate_on_contradiction: bool = True   # consolidation contradictions -> review (plan §9)
    autonomous: bool = True                  # no human-in-the-loop: never pause, commit best draft
    humanize: bool = True                    # rewrite each chapter to strip AI tells (em-dashes...)
    article_cohesion: bool = True            # whole-article smoothing pass before References
    book_cohesion: bool = True               # book: deterministic cross-chapter repetition report
    #                                          after assembly (detector, not a rewriter - a full
    #                                          10-chapter rewrite is impractical/lossy; D-008)
    use_images: bool = True                  # fetch Wikimedia Commons images (non-fiction/illustrated)
    diagram_engine: str = "auto"             # SVG layout: auto (D2+ELK if d2 is installed, else builtin) | d2 | builtin
    use_embeddings: bool = False             # semantic skill retrieval (requires sentence-transformers)
    use_headroom: bool = False              # context compression via headroom-ai. Default OFF: our calls are
    #                                         single-turn (system+user), where headroom saves ~nothing, and it
    #                                         can perturb the system prefix and defeat provider prompt-caching.
    request_timeout: float = 60.0           # per-LLM-request network timeout (seconds)
    max_run_tokens: int = 0                 # pause a run once its total tokens exceed this (0 = unlimited)
    max_context_chars: int = 24000          # budget for the assembled canon+summaries+excerpts block
    #                                         (drops lowest-priority parts first); guards against blowing
    #                                         the model window on long books. 0 = unbounded.
    mode: str = "article"        # "book" | "article" - default for new projects
    num_sections: int = 6        # default section count for articles
    theme: str = "editorial"     # TUI color theme (see ui.THEMES; /theme to switch)
    provider: str = "openrouter" # model host (see providers.py; /provider to switch)
    openrouter_providers: str = ""  # comma-separated OpenRouter upstreams to pin (e.g. "DeepSeek")
    #                                 so DeepSeek's prompt cache engages; "" = OpenRouter default routing
    export_dir: str = ""         # default save folder for exports ("" = each project's own folder; /path)
    strip_inline_citations: bool = True   # remove [N] markers from prose; sourcing lives only in end References
    rank_references: bool = True          # final References scored by influence (0-100), dated, sorted high->low
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


def load_config() -> ModelConfig:
    if not _MODELS.exists():
        return ModelConfig({})   # sensible defaults; mirrors load_settings' guard
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
    s.num_chapters = max(1, s.num_chapters)
    s.num_sections = max(1, s.num_sections)
    s.max_revisions = max(0, s.max_revisions)
    s.consolidate_every = max(1, s.consolidate_every)
    s.divergent_drafts = max(1, s.divergent_drafts)
    s.min_insight = min(5, max(0, s.min_insight))            # 0 = off; the scale is 1-5
    s.escalate_below_confidence = min(1.0, max(0.0, s.escalate_below_confidence))
    s.request_timeout = s.request_timeout if s.request_timeout > 0 else 60.0
    s.max_run_tokens = max(0, s.max_run_tokens)              # 0 = unlimited
    s.max_context_chars = max(0, s.max_context_chars)        # 0 = unbounded
    s.agentic_max_unit_steps = max(0, s.agentic_max_unit_steps)
    if s.mode not in ("book", "article"):
        s.mode = "article"
    if s.agentic_policy not in ("default", "llm", "trace"):
        s.agentic_policy = "default"
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
