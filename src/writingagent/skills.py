"""Skill library + efficacy tracking (plan §8).

Skills are markdown pages under users/<uid>/skills/. Efficacy counters live in a sidecar
users/<uid>/skills_index.json. Promotion is lift-over-baseline:
  candidate -> trusted : applied>=5 and p_skill>=p_base and target_failures==0
  -> retired           : applied>=5 and (p_base - p_skill > 0.2 or target_failures>=2)
(v1: target_failures stays 0 - we don't yet attribute a critic finding to a skill's target.)
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import brain, retrieval
from .schemas import SkillProposal

MIN_SAMPLE = 5
RETIRE_GAP = 0.2

# Ablation-duel efficacy (the causal signal): a skill is A/B-tested by drafting one
# variant WITH it and one WITHOUT (same prompt/temperature), and letting the critic say
# which is better. Win-rate is Laplace-smoothed and gated by a minimum sample so a couple
# of noisy duels can't flip a skill. This is preferred over the confounded first_pass rate.
MIN_DUELS = 5
TRUST_WR = 0.55
RETIRE_WR = 0.45


def _duel_wr(counts: dict) -> float:
    """Laplace-smoothed duel win-rate (prior = 0.5), so 0 duels reads as 0.5, not 0/1."""
    d = counts.get("duels", 0)
    return (counts.get("duel_wins", 0) + 1) / (d + 2)


def _index_path(uid: str):
    return brain.user_dir(uid) / "skills_index.json"


def seed_builtin(uid: str) -> int:
    """Copy the bundled seed skills (resources/seeds/skills/) into the user's library
    if absent. The bundle is the single source; the copies in the user's brain library
    are the editable location."""
    src = Path(__file__).resolve().parent / "resources" / "seeds" / "skills"
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


def record_duel(uid: str, name: str, won: bool) -> None:
    """Record one ablation-duel outcome: the draft WITH this skill beat (won) or lost to
    the same draft with it held out. A true counterfactual - the causal efficacy signal,
    unlike the chapter-level first_pass rate which credits every applied skill equally.
    A loss also counts as a target_failure (an *attributed* failure, at last)."""
    idx = load_index(uid)
    s = idx["skills"].setdefault(name, {"applied": 0, "first_pass": 0, "target_failures": 0})
    s["duels"] = s.get("duels", 0) + 1
    s["duel_wins"] = s.get("duel_wins", 0) + (1 if won else 0)
    if not won:
        s["target_failures"] = s.get("target_failures", 0) + 1
    save_index(uid, idx)


def pick_duel_target(uid: str, names: list[str]) -> str | None:
    """Choose which retrieved skill to A/B-test this unit: the least-dueled one that
    hasn't reached MIN_DUELS yet (None once every retrieved skill is decided). Focuses the
    limited duel budget on still-undecided candidates and tapers off on its own."""
    if not names:
        return None
    skills = load_index(uid)["skills"]
    pending = sorted(
        (skills.get(n, {}).get("duels", 0), n)
        for n in names if skills.get(n, {}).get("duels", 0) < MIN_DUELS
    )
    return pending[0][1] if pending else None


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
        duels = counts.get("duels", 0)
        p_skill = (counts["first_pass"] / applied) if applied else 0.0
        new = status
        if status == "retired":
            pass
        elif duels >= MIN_DUELS:
            # Causal signal available: decide on the (smoothed) ablation win-rate.
            wr = _duel_wr(counts)
            new = "trusted" if wr >= TRUST_WR else "retired" if wr <= RETIRE_WR else "candidate"
        elif applied >= MIN_SAMPLE:
            # Fallback while no duel data exists: the (confounded) first_pass lift rule.
            if (pbase - p_skill) > RETIRE_GAP or counts.get("target_failures", 0) >= 2:
                new = "retired"
            elif p_skill >= pbase and counts.get("target_failures", 0) == 0:
                new = "trusted"
            else:
                new = "candidate"
        if new != status:
            brain.write_text(p, _set_status(text, new))
        out.append((name, new))
    return out


DEDUP_SIM = 0.85   # Jaccard over body tokens above which two skills are "near-duplicate".


def _skill_tokens(body: str) -> set:
    """Content words (>=4 letters) from a skill's body, frontmatter stripped."""
    text = re.sub(r"(?s)^---.*?---", "", body)
    return {w for w in re.findall(r"[a-z]{4,}", text.lower())}


def _skill_score(counts: dict) -> tuple:
    """Rank key for keeping the best of a duplicate cluster: proven win-rate first (0.5 prior
    when never dueled), then how often it was applied. Higher is better."""
    return (_duel_wr(counts), counts.get("applied", 0))


def distill(uid: str) -> list[tuple[str, str]]:
    """Retire near-duplicate skills (keep the best-scoring of each cluster) so retrieval stays
    sharp as the library grows. Deterministic and NON-destructive: only flips status to
    'retired' (the md file is kept and can be reinstated). Prefers skills with proven duel
    win-rates, so it's only meaningful once duels have run. Returns [(retired, kept)]."""
    sdir = brain.skills_dir(uid)
    if not sdir.exists():
        return []
    skills = load_index(uid)["skills"]
    items = []   # (path, name, text, tokens, score)
    for p in sorted(sdir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = retrieval._parse_frontmatter(text)
        if str(fm.get("status") or "candidate") == "retired":
            continue
        name = str(fm.get("name") or p.stem)
        items.append((p, name, text, _skill_tokens(text), _skill_score(skills.get(name, {}))))

    retired: list[tuple[str, str]] = []
    dropped: set[int] = set()
    for i in range(len(items)):
        if i in dropped:
            continue
        for j in range(i + 1, len(items)):
            if j in dropped:
                continue
            ti, tj = items[i][3], items[j][3]
            union = ti | tj
            sim = len(ti & tj) / len(union) if union else 0.0
            if sim < DEDUP_SIM:
                continue
            lo = i if items[i][4] < items[j][4] else j   # retire the weaker
            keep = j if lo == i else i
            dropped.add(lo)
            brain.write_text(items[lo][0], _set_status(items[lo][2], "retired"))
            retired.append((items[lo][1], items[keep][1]))
            if lo == i:
                break
    return retired


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
            "duels": c.get("duels", 0), "duel_wr": round(_duel_wr(c), 2),
        })
    return rows
