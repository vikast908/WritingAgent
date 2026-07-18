"""Bundled shipped defaults (src/writingagent/resources/) - the single source for
models.yaml (copied out to the user config on first load, so /model edits land in a
real, user-editable file) and the seed skills (read in place)."""
from pathlib import Path

from writingagent import brain, config, skills

BUNDLED = Path(config.__file__).resolve().parent / "resources"

# ── The bundle must actually ship ────────────────────────────────────────────
def test_bundled_defaults_present():
    assert (BUNDLED / "models.yaml").exists()
    assert len(sorted((BUNDLED / "seeds" / "skills").glob("*.md"))) == 13

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

# ── seed skills install from the bundle ──────────────────────────────────────
def test_seed_builtin_installs_bundled(tmp_brain):
    n = skills.seed_builtin("default")
    assert n == 13
    installed = sorted(p.name for p in brain.skills_dir("default").glob("*.md"))
    assert "no-ai-slop.md" in installed
