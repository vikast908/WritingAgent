"""Bundled shipped defaults (src/writingagent/resources/): pip installs have no
repo-root config/ or seeds/, so the wheel carries copies - models.yaml is copied out
on first load (user-editable, /model writes land there), seed skills are read in
place. The sync tests pin the bundled copies byte-identical to the repo-root
originals so the two can never drift (the repo files stay the ones you edit)."""
from pathlib import Path

import pytest

from writingagent import brain, config, skills

REPO_ROOT = Path(config.__file__).resolve().parents[2]
BUNDLED = Path(config.__file__).resolve().parent / "resources"

needs_repo = pytest.mark.skipif(
    not (REPO_ROOT / "config" / "models.yaml").exists(),
    reason="repo-root originals absent (running from an installed package)",
)


# ── Sync: bundled copies must match the repo-root originals ─────────────────
@needs_repo
def test_bundled_models_yaml_matches_repo():
    repo = (REPO_ROOT / "config" / "models.yaml").read_text(encoding="utf-8")
    bundled = (BUNDLED / "models.yaml").read_text(encoding="utf-8")
    assert bundled == repo, (
        "src/writingagent/resources/models.yaml drifted from config/models.yaml - "
        "edit config/models.yaml and re-copy it into resources/"
    )


@needs_repo
def test_bundled_seeds_match_repo():
    repo_dir = REPO_ROOT / "seeds" / "skills"
    repo_names = sorted(p.name for p in repo_dir.glob("*.md"))
    bundled_names = sorted(p.name for p in (BUNDLED / "seeds" / "skills").glob("*.md"))
    assert bundled_names == repo_names
    for name in repo_names:
        assert (BUNDLED / "seeds" / "skills" / name).read_text(encoding="utf-8") == (
            repo_dir / name
        ).read_text(encoding="utf-8"), f"bundled seed drifted: {name}"


# ── models.yaml copy-on-first-run ────────────────────────────────────────────
def test_load_config_copies_bundled_models_on_first_run(tmp_path, monkeypatch):
    target = tmp_path / "config" / "models.yaml"
    monkeypatch.setattr(config, "_MODELS", target)
    cfg = config.load_config()
    assert target.exists(), "bundled models.yaml was not copied out"
    assert cfg.fallback == "deepseek/deepseek-v4-flash"
    assert cfg.resolved_for("writer") == "deepseek/deepseek-v4-pro"
    # Second load reads the copied file (no re-copy needed, still routed).
    assert config.load_config().resolved_for("critic") == "deepseek/deepseek-v4-pro"


def test_load_config_bare_defaults_when_nothing_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_MODELS", tmp_path / "config" / "models.yaml")
    monkeypatch.setattr(config, "_BUNDLED", tmp_path / "no-resources")
    cfg = config.load_config()
    assert cfg.fallback == ""          # the pre-bundling degraded behavior, unchanged
    assert cfg.resolved_for("writer") == cfg.default


def test_load_config_reads_bundled_when_copy_fails(tmp_path, monkeypatch):
    """A read-only install dir must still yield the bundled routing, not bare defaults."""
    monkeypatch.setattr(config, "_MODELS", tmp_path / "config" / "models.yaml")
    import shutil as _shutil

    def _boom(src, dst):
        raise OSError("read-only")

    monkeypatch.setattr(_shutil, "copyfile", _boom)
    cfg = config.load_config()
    assert cfg.fallback == "deepseek/deepseek-v4-flash"
    assert not (tmp_path / "config" / "models.yaml").exists()


# ── seed skills bundled fallback ─────────────────────────────────────────────
def test_seed_builtin_falls_back_to_bundled(tmp_path, monkeypatch, tmp_brain):
    monkeypatch.setattr(brain, "_ROOT", tmp_path / "no-repo")   # no repo-root seeds/
    n = skills.seed_builtin("default")
    assert n == 13
    installed = sorted(p.name for p in brain.skills_dir("default").glob("*.md"))
    assert "no-ai-slop.md" in installed
