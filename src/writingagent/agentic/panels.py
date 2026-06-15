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
