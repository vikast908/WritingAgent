"""Step 3 of the blind A/B: anonymize each case into A.md / B.md and write a score sheet.

For every case with BOTH sides filled, it randomly maps {writingagent, chatgpt} -> {A, B},
strips obvious format tells (so you judge substance, not which tool it is), writes A.md and
B.md, records the mapping in .blind_key.json (don't peek), and appends the case to
score_sheet.md. Score blind (see SCORING.md), then run tally.py.

    python benchmarks/blind_ab/blind.py
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

_READ_TIME = re.compile(r"(?im)^\*\*Estimated read time:.*$\n?")
_REF_SCORE = re.compile(r"(?m)^(\s*\d+\.)\s+\*\*\d+\*\*\s*·\s*[^·]*·\s*")
_RANK_NOTE = re.compile(r"(?im)^\*Ranked by influence.*$\n?")


def _strip_tells(md: str) -> str:
    """Remove the few Writing-Agent-specific format tells so the read is blind:
    the read-time header, the influence-score prefix on references, and the rank note."""
    md = _READ_TIME.sub("", md)
    md = _RANK_NOTE.sub("", md)
    md = _REF_SCORE.sub(r"\1 ", md)            # "1. **87** · 2024 · [t](u)" -> "1. [t](u)"
    return md.strip() + "\n"


def main() -> None:
    cases = HERE / "cases"
    if not cases.exists():
        raise SystemExit("No cases/ - run generate.py first.")
    key: dict = {}
    sheet = ["# Blind A/B score sheet",
             "",
             "Read A.md and B.md for each case (don't open writingagent.md / chatgpt.md).",
             "Fill `winner` = A, B, or tie. Scores 1-5 are optional (see SCORING.md).",
             "When done: `python benchmarks/blind_ab/tally.py`"]
    n = 0
    for d in sorted(p for p in cases.iterdir() if p.is_dir()):
        wa, cg = d / "writingagent.md", d / "chatgpt.md"
        if not wa.exists() or not cg.exists():
            print(f"skip (missing a side): {d.name}")
            continue
        cgtext = cg.read_text(encoding="utf-8")
        if "PASTE ChatGPT" in cgtext or not cgtext.strip():
            print(f"skip (chatgpt.md not filled): {d.name}")
            continue
        sides = [("writingagent", _strip_tells(wa.read_text(encoding="utf-8"))),
                 ("chatgpt", _strip_tells(cgtext))]
        random.shuffle(sides)
        (d / "A.md").write_text(sides[0][1], encoding="utf-8")
        (d / "B.md").write_text(sides[1][1], encoding="utf-8")
        key[d.name] = {"A": sides[0][0], "B": sides[1][0]}
        sheet += [f"\n## {d.name}",
                  "- winner (A/B/tie): ",
                  "- A  insight: _  trust: _  readability: _",
                  "- B  insight: _  trust: _  readability: _"]
        n += 1
    if not n:
        raise SystemExit("No ready cases (fill the chatgpt.md placeholders first).")
    (HERE / ".blind_key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    (HERE / "score_sheet.md").write_text("\n".join(sheet) + "\n", encoding="utf-8")
    print(f"Wrote score_sheet.md ({n} cases) + .blind_key.json. Score blind, then run tally.py.")


if __name__ == "__main__":
    main()
