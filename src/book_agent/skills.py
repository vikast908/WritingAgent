"""Skill library + efficacy tracking (plan §8).

Skills are markdown pages under users/<uid>/skills/. Efficacy counters live in a sidecar
users/<uid>/skills_index.json. Promotion is lift-over-baseline:
  candidate -> trusted : applied>=5 and p_skill>=p_base and target_failures==0
  -> retired           : applied>=5 and (p_base - p_skill > 0.2 or target_failures>=2)
(v1: target_failures stays 0 - we don't yet attribute a critic finding to a skill's target.)
"""
from __future__ import annotations

import re

import yaml

from . import brain, retrieval
from .schemas import SkillProposal

MIN_SAMPLE = 5
RETIRE_GAP = 0.2


def _index_path(uid: str):
    return brain.user_dir(uid) / "skills_index.json"


def seed_builtin(uid: str) -> int:
    """Copy built-in seed skills (seeds/skills/) into the user's library if absent."""
    src = brain._ROOT / "seeds" / "skills"
    if not src.exists():
        return 0
    brain.ensure_user(uid)
    dst = brain.skills_dir(uid)
    n = 0
    for p in src.glob("*.md"):
        target = dst / p.name
        if not target.exists():
            target.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            n += 1
    return n


def load_index(uid: str) -> dict:
    return brain.read_json(_index_path(uid)) or {
        "_baseline": {"chapters": 0, "first_pass": 0},
        "skills": {},
    }


def save_index(uid: str, idx: dict) -> None:
    brain.write_json(_index_path(uid), idx)


def record_chapter(uid: str, applied_names: list[str], first_pass: bool) -> None:
    idx = load_index(uid)
    b = idx["_baseline"]
    b["chapters"] += 1
    b["first_pass"] += 1 if first_pass else 0
    for name in applied_names:
        s = idx["skills"].setdefault(name, {"applied": 0, "first_pass": 0, "target_failures": 0})
        s["applied"] += 1
        s["first_pass"] += 1 if first_pass else 0
    save_index(uid, idx)


def write_skill(uid: str, prop: SkillProposal) -> None:
    brain.ensure_user(uid)
    # Serialize frontmatter with yaml so a name/tag containing :, ], #, etc. can't
    # produce malformed frontmatter that _parse_frontmatter then silently drops.
    fm = yaml.safe_dump(
        {"name": prop.name, "genre_tags": list(prop.genre_tags), "status": "candidate"},
        sort_keys=False, allow_unicode=True, default_flow_style=False,
    ).strip()
    lines = [
        "---", fm, "---", "",
        "## When to apply", prop.when_to_apply, "",
        "## Technique", *(f"- {t}" for t in prop.technique), "",
        "## Anti-pattern it replaces", prop.anti_pattern,
    ]
    sdir = brain.skills_dir(uid)
    slug = brain.slugify(prop.name)
    # Avoid clobbering a *different* skill that happens to slug identically.
    target = sdir / f"{slug}.md"
    if target.exists():
        existing = retrieval._parse_frontmatter(target.read_text(encoding="utf-8"))
        if str(existing.get("name") or "") not in ("", prop.name):
            n = 2
            while (sdir / f"{slug}-{n}.md").exists():
                n += 1
            target = sdir / f"{slug}-{n}.md"
    brain.write_text(target, "\n".join(lines))


def _p_base(idx: dict) -> float:
    b = idx["_baseline"]
    return (b["first_pass"] / b["chapters"]) if b["chapters"] else 0.0


def _set_status(text: str, new: str) -> str:
    return re.sub(r"(?m)^status:.*$", f"status: {new}", text, count=1)


def reconcile(uid: str) -> list[tuple[str, str]]:
    """Apply promotion/retirement rules; rewrite skill md status. Returns [(name, status)]."""
    sdir = brain.skills_dir(uid)
    if not sdir.exists():
        return []
    idx = load_index(uid)
    pbase = _p_base(idx)
    out: list[tuple[str, str]] = []
    for p in sdir.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        fm = retrieval._parse_frontmatter(text)
        name = str(fm.get("name") or p.stem)
        status = str(fm.get("status") or "candidate")
        counts = idx["skills"].get(name, {"applied": 0, "first_pass": 0, "target_failures": 0})
        applied = counts["applied"]
        p_skill = (counts["first_pass"] / applied) if applied else 0.0
        new = status
        if status != "retired" and applied >= MIN_SAMPLE:
            if (pbase - p_skill) > RETIRE_GAP or counts["target_failures"] >= 2:
                new = "retired"
            elif p_skill >= pbase and counts["target_failures"] == 0:
                new = "trusted"
            else:
                new = "candidate"
        if new != status:
            brain.write_text(p, _set_status(text, new))
        out.append((name, new))
    return out


def list_skills(uid: str) -> list[dict]:
    sdir = brain.skills_dir(uid)
    if not sdir.exists():
        return []
    idx = load_index(uid)
    pbase = _p_base(idx)
    rows = []
    for p in sorted(sdir.glob("*.md")):
        fm = retrieval._parse_frontmatter(p.read_text(encoding="utf-8"))
        name = str(fm.get("name") or p.stem)
        c = idx["skills"].get(name, {"applied": 0, "first_pass": 0})
        p_skill = (c["first_pass"] / c["applied"]) if c["applied"] else 0.0
        rows.append({
            "name": name, "status": str(fm.get("status") or "candidate"),
            "applied": c["applied"], "p_skill": round(p_skill, 2), "p_base": round(pbase, 2),
        })
    return rows
