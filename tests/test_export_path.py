"""Configurable save location for exports: the global default, per-project
overrides, the safe move of existing deliverables, and export redirection.

The brain `manuscript.md` source and all working files must NEVER move - only the
rendered deliverables (pdf/epub/.../manuscript_export.md) relocate."""
from pathlib import Path

import pytest

from writingagent import brain, orchestrator
from writingagent.config import Settings


def _make_article(uid: str, pid: str) -> Path:
    root = brain.user_dir(uid) / "articles" / pid
    root.mkdir(parents=True, exist_ok=True)
    (root / "run_state.json").write_text('{"mode":"article"}', encoding="utf-8")
    (root / "manuscript.md").write_text("# Title\n\nSome body text.", encoding="utf-8")
    return root


def test_project_root_detects_article_vs_book(tmp_brain):
    root = _make_article("u", "art1")
    assert brain.project_root("u", "art1") == root
    # a project without an article run_state resolves to the book root
    assert brain.project_root("u", "bk1") == brain.user_dir("u") / "books" / "bk1"


def _no_global_default(monkeypatch):
    """Pin load_settings so the root-fallback tests don't see an ambient export_dir."""
    monkeypatch.setattr("writingagent.config.load_settings", Settings)


def test_default_export_dir_is_project_root(tmp_brain, monkeypatch):
    _no_global_default(monkeypatch)
    root = _make_article("u", "demo")
    assert brain.resolve_export_dir("u", "demo") == root        # unchanged original behaviour


def test_per_project_override_wins(tmp_brain, tmp_path, monkeypatch):
    _no_global_default(monkeypatch)
    _make_article("u", "demo")
    dest = tmp_path / "Saved"
    brain.set_project_export_dir("u", "demo", str(dest))
    assert brain.resolve_export_dir("u", "demo") == dest
    assert dest.exists()                                        # resolve ensures the dir
    assert brain.get_project_export_dir("u", "demo") == str(dest)
    brain.set_project_export_dir("u", "demo", None)             # clear -> back to root
    assert brain.get_project_export_dir("u", "demo") is None
    assert brain.resolve_export_dir("u", "demo") == brain.project_root("u", "demo")


def test_global_default_namespaces_by_project(tmp_brain, tmp_path, monkeypatch):
    _make_article("u", "demo")
    base = tmp_path / "AllWriting"
    monkeypatch.setattr("writingagent.config.load_settings",
                        lambda: Settings(export_dir=str(base)))
    assert brain.resolve_export_dir("u", "demo") == base / "demo"


def test_move_relocates_deliverables_but_not_source(tmp_brain, tmp_path):
    root = _make_article("u", "demo")
    (root / "manuscript.pdf").write_bytes(b"%PDF old")
    (root / "manuscript.epub").write_bytes(b"PK old")
    dest = tmp_path / "Out"
    moved = brain.move_exports(root, dest)
    assert sorted(moved) == ["manuscript.epub", "manuscript.pdf"]
    assert (dest / "manuscript.pdf").exists() and (dest / "manuscript.epub").exists()
    assert not (root / "manuscript.pdf").exists()
    assert (root / "manuscript.md").exists()                    # source stays put
    assert (root / "run_state.json").exists()                   # working state stays put


def test_move_is_noop_for_same_dir(tmp_brain):
    root = _make_article("u", "demo")
    (root / "manuscript.pdf").write_bytes(b"%PDF")
    assert brain.move_exports(root, root) == []                 # nothing to do, no error


@pytest.mark.parametrize("fmt,fn", [("md", orchestrator.export_md),
                                    ("txt", orchestrator.export_txt)])
def test_export_writes_to_override_dir(tmp_brain, tmp_path, fmt, fn):
    _make_article("u", "demo")
    dest = tmp_path / "Deliverables"
    brain.set_project_export_dir("u", "demo", str(dest))
    out = fn("u", "demo")
    assert Path(out).parent == dest                             # rendered file lands in the override
    assert Path(out).exists()
