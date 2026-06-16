"""Few-shot demonstrations injected into craft prompts (plan §22).

Weak models *imitate*; they do not reliably follow abstract instructions. A rule like
"score insight 1-5" or "remove AI tells" is a coin-flip on a basic model; the same model
shown two or three concrete before/after pairs (or a 5-vs-2 anchor) calibrates far better.
These blocks are short and stable, so they live in the system prompt (provider prompt-cache
keeps them ~free across calls). The genre *style* anchor is delivered separately by the gold
corpus (registers.gold_exemplars) through the voice-exemplar slot.
"""
from __future__ import annotations

# ── Humanizer: AI-tell → human rewrite (manner of the fix, not the content) ─────────
_HUMANIZER_PAIRS = [
    ("In today's fast-paced world, leveraging robust solutions is crucial for success.",
     "Teams that ship every week outlast teams that plan every quarter."),
    ("This serves as a testament to our unwavering commitment to innovation.",
     "We rewrote the parser twice and cut median latency from 800ms to 90ms."),
    ("It is worth noting that the system is highly scalable and seamlessly integrates.",
     "The system handled 40,000 requests a second in the load test, and it talks to Stripe "
     "over their standard webhook."),
    ("Furthermore, this groundbreaking approach delves into a myriad of cutting-edge techniques.",
     "The approach borrows one old trick: cache the expensive call and invalidate it on write."),
]


def humanizer_fewshot() -> str:
    """Before/after pairs showing the *manner* of a minimal de-tell rewrite."""
    lines = ["\n\nEXAMPLES (the kind of minimal rewrite wanted - keep meaning, kill the tell):"]
    for bad, good in _HUMANIZER_PAIRS:
        lines.append(f'- BEFORE: "{bad}"\n  AFTER:  "{good}"')
    return "\n".join(lines)


# ── Critic: score anchors (so even a weak judge calibrates, not rubber-stamps) ──────
# A 5 and a 2 for each scored dimension. The anchor is the calibration: "competent but
# generic" is a 3, not a 4; a specific, contestable, evidenced sentence is the 5.
_ANCHORS = {
    "insight": (
        '5: "The spreadsheet that runs the firm has 14,000 rows and one maintainer who isn\'t '
        'retiring - competence accumulates into risk."',
        '2: "Good documentation is important for long-term maintainability."'),
    "clarity": (
        '5: "A retry is not a fix; it is a louder version of the same failed request."',
        '2: "The system leverages a multifaceted approach to optimize various synergies."'),
    "structure": (
        "5: each paragraph sets up the next; the last line of one is answered by the first of the next.",
        "2: paragraphs are interchangeable - you could shuffle them and lose nothing."),
    "evidence": (
        '5: "Moving to jittered backoff cut recovery from ~90s to under 10s on a 500-node fleet."',
        '2: "This significantly improves performance and reliability."'),
}


def critic_anchors() -> str:
    """Score anchors for the critic's 1-5 dimensions. Calibration beats definitions on a
    weak judge: it stops 'competent but predictable' from sliding up to a 4."""
    lines = ["\n\nSCORE ANCHORS (calibrate against these; competent-but-generic is a 3, not a 4):"]
    for dim, (hi, lo) in _ANCHORS.items():
        lines.append(f"- {dim} {hi}")
        lines.append(f"  {dim} {lo}")
    return "\n".join(lines)
