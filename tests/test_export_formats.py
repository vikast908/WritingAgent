"""`export` accepts a single format, a list, or 'all' - and one failing format
must never abort the others. Covers the resolver, the argparse surface, and the
multi-format run (md/txt are dependency-free, so they render in any environment)."""
from types import SimpleNamespace

import pytest

from writingagent import brain, cli
from writingagent.config import load_config, load_settings


def test_resolve_formats_all_lists_and_unknowns():
    assert cli._resolve_formats("all")[0] == cli._EXPORT_FORMATS
    assert cli._resolve_formats("pdf")[0] == ["pdf"]
    assert cli._resolve_formats("pdf, epub html")[0] == ["pdf", "epub", "html"]
    # pasting the whole "pdf · epub · …" choices line resolves to every format, deduped
    assert cli._resolve_formats("pdf · epub · html · docx · txt · md")[0] == cli._EXPORT_FORMATS
    assert cli._resolve_formats("all pdf")[0] == cli._EXPORT_FORMATS          # dedup
    assert cli._resolve_formats("xyz")[0] == [] and cli._resolve_formats("xyz")[1] == ["xyz"]
    assert cli._resolve_formats("")[0] == []


def test_resolve_formats_plain_english_and_synonyms():
    # connector words, &/+ separators, and synonyms (word→docx, markdown→md, ebook→epub)
    assert cli._resolve_formats("pdf, epub and docx")[0] == ["pdf", "epub", "docx"]
    assert cli._resolve_formats("give me markdown & pdf please")[0] == ["md", "pdf"]
    assert cli._resolve_formats("i want pdf, epub and a word file")[0] == ["pdf", "epub", "docx"]
    assert cli._resolve_formats("ebook + web")[0] == ["epub", "html"]
    assert cli._resolve_formats("everything")[0] == cli._EXPORT_FORMATS
    assert cli._resolve_formats("pdf or epub")[0] == ["pdf", "epub"]
    # a genuine unknown is still reported, while the valid ones go through
    got, bad = cli._resolve_formats("pdf and banana")
    assert got == ["pdf"] and bad == ["banana"]


def test_export_argparse_accepts_positional_and_all():
    ap = cli.build_parser(load_settings())
    assert ap.parse_args(["export", "all"]).formats == ["all"]
    assert ap.parse_args(["export", "pdf", "epub"]).formats == ["pdf", "epub"]
    assert ap.parse_args(["export", "--format", "all"]).format == "all"        # no choices lock
    assert ap.parse_args(["export"]).formats == []


def _article(uid: str, pid: str):
    root = brain.user_dir(uid) / "articles" / pid
    root.mkdir(parents=True, exist_ok=True)
    (root / "run_state.json").write_text('{"mode":"article"}', encoding="utf-8")
    (root / "manuscript.md").write_text("# Title\n\nBody text here.", encoding="utf-8")
    return root


def test_export_multiple_formats_writes_each(tmp_brain, monkeypatch):
    monkeypatch.setattr(cli, "_console", lambda: None)
    root = _article("u", "demo")
    args = SimpleNamespace(book_id="demo", user="u", formats=["md", "txt"], format=None)
    cli.cmd_export(args, load_config(), load_settings(), "u")
    out = brain.resolve_export_dir("u", "demo")
    assert (out / "manuscript_export.md").exists() and (out / "manuscript.txt").exists()
    assert out == root


def test_export_all_resolves_every_format(tmp_brain, monkeypatch):
    """`export all` attempts every format; with stub exporters all are invoked."""
    monkeypatch.setattr(cli, "_console", lambda: None)
    _article("u", "demo")
    called = []
    monkeypatch.setattr(cli, "_EXPORT_FNS",
                        {f: (lambda uid, bid, _f=f: called.append(_f) or None)
                         for f in cli._EXPORT_FORMATS})
    cli.cmd_export(SimpleNamespace(book_id="demo", user="u", formats=["all"], format=None),
                   load_config(), load_settings(), "u")
    assert called == cli._EXPORT_FORMATS


def test_one_failing_format_does_not_abort_others(tmp_brain, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_console", lambda: None)
    _article("u", "demo")

    def boom(uid, bid):
        raise RuntimeError("missing dependency")
    fns = dict(cli._EXPORT_FNS)
    fns["pdf"] = boom                              # pdf blows up; md/txt must still run
    monkeypatch.setattr(cli, "_EXPORT_FNS", fns)
    cli.cmd_export(SimpleNamespace(book_id="demo", user="u",
                                   formats=["pdf", "md", "txt"], format=None),
                   load_config(), load_settings(), "u")
    out = brain.resolve_export_dir("u", "demo")
    assert (out / "manuscript_export.md").exists() and (out / "manuscript.txt").exists()
    printed = capsys.readouterr().out
    assert "FAIL] pdf" in printed and "exported 2/3 formats" in printed


def test_unknown_format_in_cli_exits(tmp_brain, monkeypatch):
    monkeypatch.setattr(cli, "_console", lambda: None)
    _article("u", "demo")
    with pytest.raises(SystemExit):
        cli.cmd_export(SimpleNamespace(book_id="demo", user="u", formats=["nope"], format=None),
                       load_config(), load_settings(), "u")
