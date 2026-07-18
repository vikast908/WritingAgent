"""Generate the `writing-personas` Claude skill from the source-of-truth persona registry.

Reads `writingagent.personas` (signature cards + register compatibility) and the
`personas/*.md` exemplars, and emits one self-contained voice file per persona under
`.claude/skills/writing-personas/voices/`, plus a catalog table (printed to stdout) for
SKILL.md. Re-run after editing personas to keep the skill in sync.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from writingagent import personas  # noqa: E402

SKILL = ROOT / ".claude" / "skills" / "writing-personas"
VOICES = SKILL / "voices"
EXEMPLAR_DIR = ROOT / "src" / "writingagent" / "resources" / "personas"


def exemplar_body(p) -> str:
    """Raw exemplar prose with the leading markdown heading line(s) stripped."""
    path = EXEMPLAR_DIR / f"{p.name}.md"
    text = path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def regs(p) -> str:
    return ", ".join(p.registers) if p.registers else "all"


def main() -> None:
    VOICES.mkdir(parents=True, exist_ok=True)
    names = personas.names()
    for name in names:
        p = personas.get(name)
        block = (
            f"# {p.name} — {p.kind}\n\n"
            f"**Compatible registers:** {regs(p)}\n\n"
            f"**In a line:** {p.description}\n\n"
            f"## Manner card\n\n{p.signature}\n\n"
            f"## Exemplar — match the rhythm, diction, and stance; do NOT copy the content\n\n"
            f"{exemplar_body(p)}\n"
        )
        (VOICES / f"{p.name}.md").write_text(block, encoding="utf-8")

    # Catalog table for SKILL.md (archetypes first, then author manners).
    def rows(kind: str) -> str:
        out = []
        for name in names:
            p = personas.get(name)
            if p.kind != kind:
                continue
            out.append(f"| `{p.name}` | {regs(p)} | {p.description} |")
        return "\n".join(out)

    arche = [n for n in names if personas.get(n).kind == "archetype"]
    auth = [n for n in names if personas.get(n).kind == "author"]
    print(f"# wrote {len(names)} voice files to {VOICES}")
    print(f"# archetypes={len(arche)} authors={len(auth)}\n")
    print("### Archetypes (original, reusable voices)\n")
    print("| Voice | Registers | In a line |")
    print("| --- | --- | --- |")
    print(rows("archetype"))
    print("\n### Public-domain author manners (the technique, never the text)\n")
    print("| Voice | Registers | In a line |")
    print("| --- | --- | --- |")
    print(rows("author"))

    # By-register index ("a voice for every genre").
    order = ["nonfiction", "technical", "literary-fiction", "genre-fiction", "academic",
             "journalism", "copywriting", "business", "poetry", "screenplay", "children"]
    by_reg: dict[str, list[str]] = {r: [] for r in order}
    for name in names:
        p = personas.get(name)
        for r in order:
            if personas.compatible(name, r):
                by_reg[r].append(p.name)
    print("\n### A voice for every register\n")
    for r in order:
        vs = ", ".join(f"`{v}`" for v in by_reg[r])
        print(f"- **{r}** — {vs}")


if __name__ == "__main__":
    main()
