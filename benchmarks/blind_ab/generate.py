"""Step 1 of the blind A/B: generate Writing Agent's side for every prompt.

Runs the REAL pipeline (needs OPENROUTER_API_KEY; ~$0.25/prompt). For each prompt it
writes cases/<slug>/writingagent.md and an empty cases/<slug>/chatgpt.md placeholder for
you to fill (Step 2). Re-running skips prompts already generated.

    python benchmarks/blind_ab/generate.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# Make book_agent importable whether or not it's pip-installed, and load the project .env.
sys.path.insert(0, str(ROOT / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from book_agent import Agent  # noqa: E402

UNITS = 4   # sections per article; bump for longer pieces (and higher cost)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "case"


def main() -> None:
    prompts = [ln.strip() for ln in (HERE / "prompts.txt").read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.startswith("#")]
    if not prompts:
        sys.exit("No prompts in prompts.txt.")
    if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("BOOK_AGENT_FAKE"):
        sys.exit("Set OPENROUTER_API_KEY (real run) or BOOK_AGENT_FAKE=1 (dry wiring test).")

    cases = HERE / "cases"
    cases.mkdir(exist_ok=True)
    agent = Agent(autonomous=True, use_images=False)   # images add network + cost

    for p in prompts:
        d = cases / slug(p)
        d.mkdir(exist_ok=True)
        (d / "prompt.txt").write_text(p, encoding="utf-8")
        if (d / "writingagent.md").exists():
            print(f"skip (already generated): {p}")
        else:
            print(f"\n=== generating: {p}")
            proj = agent.create(p, mode="article", units=UNITS, project_id=f"ab-{slug(p)}")
            try:
                proj.run(progress=lambda m: print("   ", str(m).strip()))
                md = proj.export("md")
                (d / "writingagent.md").write_text(Path(md).read_text(encoding="utf-8"),
                                                   encoding="utf-8")
            finally:
                proj.delete()   # the .md is saved; don't leave the project in the brain
        cg = d / "chatgpt.md"
        if not cg.exists():
            cg.write_text("<!-- PASTE ChatGPT/Claude's reply to this exact prompt here, then "
                          "delete this comment line. -->\n", encoding="utf-8")

    print("\nDone. Step 2: paste each competitor reply into cases/<slug>/chatgpt.md, "
          "then run blind.py")


if __name__ == "__main__":
    main()
