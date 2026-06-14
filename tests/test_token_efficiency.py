"""Tests for the token-efficiency pass: cache telemetry, lossless schema shrink,
thesis brief, per-node max_tokens, and the skeleton-draft helper wiring."""
from __future__ import annotations

from types import SimpleNamespace

from writingagent import llm, nodes
from writingagent import schemas as S
from writingagent.config import ModelConfig


def test_strip_schema_noise_drops_titles_keeps_structure():
    raw = {"title": "Foo", "type": "object",
           "properties": {"x": {"title": "X", "type": "integer"}},
           "required": ["x"]}
    out = llm._strip_schema_noise(raw)
    assert "title" not in out and "title" not in out["properties"]["x"]
    assert out["properties"]["x"]["type"] == "integer"      # types/required preserved
    assert out["required"] == ["x"]


def test_json_instruction_strips_titles_keeps_fields():
    s = llm._json_instruction(S.Critique)
    assert '"title"' not in s                                # lossless shrink
    assert "verdict" in s and "blocking" in s and "insight" in s


def test_cached_tokens_reads_details_object_or_dict():
    assert llm._cached_tokens(SimpleNamespace(
        prompt_tokens_details=SimpleNamespace(cached_tokens=128))) == 128
    assert llm._cached_tokens(SimpleNamespace(
        prompt_tokens_details={"cached_tokens": 64})) == 64
    assert llm._cached_tokens(SimpleNamespace(prompt_tokens_details=None)) == 0
    assert llm._cached_tokens(SimpleNamespace()) == 0
    # DeepSeek-direct reports the hit under prompt_cache_hit_tokens (not in details)
    assert llm._cached_tokens(SimpleNamespace(
        prompt_tokens_details=None, prompt_cache_hit_tokens=200)) == 200
    # provider-specific fields can arrive in pydantic's model_extra
    assert llm._cached_tokens(SimpleNamespace(
        prompt_tokens_details=None, model_extra={"prompt_cache_hit_tokens": 99})) == 99


def test_openrouter_provider_routing(monkeypatch):
    monkeypatch.setattr(llm, "_include_cost", True)
    llm.configure_openrouter_providers("DeepSeek, Fireworks")
    body = llm._cost_kwargs()["extra_body"]
    assert body["usage"]["include"] is True
    assert body["provider"] == {"order": ["DeepSeek", "Fireworks"], "allow_fallbacks": True}
    llm.configure_openrouter_providers("")                      # off -> no provider pin
    assert "provider" not in llm._cost_kwargs().get("extra_body", {})
    monkeypatch.setattr(llm, "_include_cost", False)            # non-OpenRouter -> nothing sent
    assert llm._cost_kwargs() == {}


def test_usage_summary_reports_cache_hits():
    llm.reset_usage()
    u = SimpleNamespace(prompt_tokens=1000, completion_tokens=200, total_tokens=1200,
                        cost=0.0, prompt_tokens_details=SimpleNamespace(cached_tokens=400))
    llm._record_usage(SimpleNamespace(usage=u))
    s = llm.usage_summary()
    assert "cached" in s and "400" in s
    llm.reset_usage()


def test_max_tokens_for_override_and_default():
    cfg = ModelConfig({"max_tokens": {"judge": 1234}})
    assert cfg.max_tokens_for("judge", 2000) == 1234
    assert cfg.max_tokens_for("writer", 8000) == 8000       # no override -> default
    assert ModelConfig({}).max_tokens_for("anything", 9) == 9
    assert "max_tokens" in cfg.to_dict()                    # round-trips for save_config


def test_build_evidence_report():
    from writingagent import polish
    ms = ("# My Title\n\n*angle*\n\nBody.\n\n---\n\n"
          "## References\n\n*Ranked by influence on this article (0–100).*\n\n"
          "1. **100** · 2024 · [A](http://a)\n2. **40** · n.d. · [B](http://b)\n")
    thesis = "**Claim:** X beats Y.\n**Stakes:** big\n**Arguments:**\n- a"
    rep = polish.build_evidence_report(ms, thesis)
    assert "Evidence report" in rep and "My Title" in rep
    assert "X beats Y." in rep                       # the thesis is the argument
    assert "**2** sources" in rep and "high-influence" in rep
    assert "ranked by influence" in rep.lower()
    assert polish.build_evidence_report("", "") == ""   # nothing -> empty


def test_thesis_brief_keeps_claim_and_arguments_only():
    t = S.Thesis(claim="C is true.", stakes="big stakes",
                 arguments=["arg one", "arg two"], counterargument="but X",
                 rebuttal="yet Y", non_goals=["not Z"])
    brief = nodes.thesis_brief(nodes.render_thesis(t))
    assert "C is true." in brief and "arg one" in brief and "arg two" in brief
    assert "big stakes" not in brief and "but X" not in brief and "not Z" not in brief
    assert nodes.thesis_brief("") == ""
    assert nodes.thesis_brief("no headers here") == "no headers here"   # fallback
