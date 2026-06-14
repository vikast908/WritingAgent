"""Step 5 of the blind A/B: reveal the key and tally the result.

Parses your filled score_sheet.md, maps A/B back to the real tools via .blind_key.json,
and prints the win-rate (+ average dimension scores per tool). Paste the summary into
RESULTS.md to publish it.

    python benchmarks/blind_ab/tally.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

_WINNER = re.compile(r"winner\s*\(a/b/tie\)\s*:\s*([ab]|tie)\b", re.I)
_SCORES = re.compile(r"^-\s*([AB])\b.*?insight:\s*(\d).*?trust:\s*(\d).*?readability:\s*(\d)", re.I)


def main() -> None:
    key_path = HERE / ".blind_key.json"
    sheet_path = HERE / "score_sheet.md"
    if not key_path.exists() or not sheet_path.exists():
        raise SystemExit("Run blind.py and fill score_sheet.md first.")
    key = json.loads(key_path.read_text(encoding="utf-8"))
    sheet = sheet_path.read_text(encoding="utf-8")

    wins = {"writingagent": 0, "chatgpt": 0, "tie": 0}
    dims = {"writingagent": [0, 0, 0, 0], "chatgpt": [0, 0, 0, 0]}  # insight, trust, read, count
    cur = None
    for line in sheet.splitlines():
        m = re.match(r"^##\s+(.+)$", line.strip())
        if m:
            cur = m.group(1).strip()
            continue
        if not cur or cur not in key:
            continue
        w = _WINNER.search(line)
        if w:
            v = w.group(1).lower()
            wins["tie" if v == "tie" else key[cur][v.upper()]] += 1
        s = _SCORES.search(line)
        if s:
            tool = key[cur][s.group(1).upper()]
            for i in range(3):
                dims[tool][i] += int(s.group(i + 2))
            dims[tool][3] += 1

    n = sum(wins.values())
    print(f"Cases scored: {n}\n")
    if not n:
        raise SystemExit("No 'winner:' lines filled in score_sheet.md yet.")
    for k in ("writingagent", "chatgpt", "tie"):
        print(f"  {k:13} {wins[k]}  ({100 * wins[k] / n:.0f}%)")
    decisive = wins["writingagent"] + wins["chatgpt"]
    if decisive:
        print(f"\n  Writing Agent win-rate (excl. ties): "
              f"{100 * wins['writingagent'] / decisive:.0f}%  ({wins['writingagent']}/{decisive})")
    print("\n  avg scores (insight / trust / readability):")
    for tool in ("writingagent", "chatgpt"):
        c = dims[tool][3]
        if c:
            i, t, r = (dims[tool][j] / c for j in range(3))
            print(f"    {tool:13} {i:.1f} / {t:.1f} / {r:.1f}  (n={c})")


if __name__ == "__main__":
    main()
