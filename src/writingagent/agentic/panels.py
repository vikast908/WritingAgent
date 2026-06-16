"""Multi-agent verification panels (plan.md §21.10).

Where independent perspectives beat one pass. The fact-check panel is the honest
Phase-4 unit: N independent claim audits over the SAME draft, majority-vote, reusing
the existing `verify_claims` node - not free-form agent-to-agent chatter. Exposed as a
public utility behind the `agentic_factcheck_panel` setting.
"""
from __future__ import annotations

from .. import concurrency, nodes


def fact_check_panel(cfg, draft: str, source_text: str, *, voters: int = 3,
                     log=print) -> tuple[bool, int]:
    """Adversarial fact-check: run `voters` independent claim audits; the draft passes
    only if a MAJORITY find no unsupported cited claim. Returns (passed, refute_votes).
    No-op pass when there is nothing to check (no draft or no source ground truth)."""
    voters = max(1, voters)
    if not source_text or not draft:
        return True, 0

    def _refutes() -> bool:
        try:
            audit = nodes.verify_claims(cfg, draft, source_text)
        except Exception:  # noqa: BLE001 - a verifier that errors is not a refutation
            return False
        return any(c.supported == "unsupported" for c in audit.checks)

    votes = concurrency.gather({f"v{i}": _refutes for i in range(voters)})
    refutes = sum(1 for v in votes.values() if v)
    passed = refutes < (voters / 2.0)   # a clean majority is required
    log(f"   [panel] fact-check: {voters - refutes}/{voters} verifiers clean "
        f"-> {'pass' if passed else 'block'}")
    return passed, refutes


#: Distinct reviewer lenses for the critique panel - decorrelated blind spots beat one pass.
CRITIQUE_LENSES: tuple[str, ...] = (
    "a skeptical domain expert checking every claim for rigor",
    "a first-time reader who needs each idea made clear and concrete",
    "a sharp editor hunting for filler, vagueness, and unsupported assertions",
)


def critique_panel(critique_fn, *, lenses: tuple[str, ...] = CRITIQUE_LENSES,
                   log=print) -> tuple[bool, int]:
    """Diverse-perspective critique (plan §21.10): run independent critics over the SAME draft,
    each through a distinct lens, and BLOCK only if a majority raise a blocking concern - so one
    lens's blind spot can't sink a good draft, and a real flaw seen by most still blocks.
    `critique_fn(lens) -> Critique`. Returns (passed, block_votes)."""
    def _blocks(lens: str) -> bool:
        try:
            crit = critique_fn(lens)
        except Exception:  # noqa: BLE001 - a critic that errors is not a block
            return False
        return crit.verdict != "approve" or bool(crit.blocking)

    votes = concurrency.gather({f"c{i}": (lambda ln=ln: _blocks(ln)) for i, ln in enumerate(lenses)})
    blocks = sum(1 for v in votes.values() if v)
    passed = blocks < (len(lenses) / 2.0)
    log(f"   [panel] critique: {len(lenses) - blocks}/{len(lenses)} lenses clear "
        f"-> {'pass' if passed else 'block'}")
    return passed, blocks
