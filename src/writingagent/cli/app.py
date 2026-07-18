"""CLI wiring: the command registry, the argparse surface, provider selection,
and the `main()` entry point (bare invocation drops into the interactive shell)."""
from __future__ import annotations

import argparse
import sys

from .. import brain, ui
from ..config import load_config, load_settings
from .commands import (
    cmd_brief,
    cmd_config,
    cmd_consolidate,
    cmd_delete,
    cmd_eval,
    cmd_list,
    cmd_memory,
    cmd_produce,
    cmd_read,
    cmd_review,
    cmd_revise,
    cmd_run,
    cmd_seed_skills,
    cmd_skills,
    cmd_status,
    cmd_tableread,
    cmd_versions,
)
from .create import cmd_new
from .export import cmd_evidence, cmd_export, cmd_polish, cmd_promote, cmd_seo
from .interview import cmd_write

__all__ = ["_COMMANDS", "build_parser", "_apply_provider", "main"]


def cmd_web(args, cfg, settings, uid):
    """Serve the local web dashboard (run the pipeline + evals/traces/cost in a browser)."""
    from ..webui import serve
    serve(port=getattr(args, "port", 8787),
          open_browser=not getattr(args, "no_browser", False))


_COMMANDS = {
    "new": cmd_new, "write": cmd_write, "run": cmd_run, "status": cmd_status, "review": cmd_review,
    "revise": cmd_revise, "versions": cmd_versions, "brief": cmd_brief,
    "tableread": cmd_tableread, "eval": cmd_eval,
    "read": cmd_read, "memory": cmd_memory, "produce": cmd_produce,
    "consolidate": cmd_consolidate, "skills": cmd_skills, "config": cmd_config,
    "list": cmd_list, "export": cmd_export, "seed-skills": cmd_seed_skills,
    "delete": cmd_delete, "polish": cmd_polish, "evidence": cmd_evidence,
    "seo": cmd_seo, "promote": cmd_promote, "web": cmd_web,
}


def build_parser(settings):
    ap = argparse.ArgumentParser(prog="writing-agent", description="Writing Agent CLI (see plan.md §13).")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--user", default=settings.default_user)
    common.add_argument("--book-id")
    common.add_argument("--plain", action="store_true", help="Disable colour/styling")
    sub = ap.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", parents=[common], help="Create a book (plan + TOC)")
    p_new.add_argument("--abstract")
    p_new.add_argument("--pick", type=int)
    p_new.add_argument("--chapters", type=int)
    p_new.add_argument("--max-revisions", type=int)
    # Tri-state so the settings.autonomous default isn't shadowed by a store_true False.
    p_new.add_argument("--autonomous", dest="autonomous", action="store_const", const=True,
                       default=None, help="Never pause; commit the best draft (overrides setting)")
    p_new.add_argument("--no-autonomous", dest="autonomous", action="store_const", const=False,
                       help="Force human-in-the-loop review (overrides settings.autonomous)")
    p_new.add_argument("--no-humanize", action="store_true",
                       help="Skip the humanizer pass that strips AI tells")

    # `write`: interview once, then run fully autonomously to a finished, exported file.
    p_write = sub.add_parser(
        "write", parents=[common],
        help="Interview upfront, then autonomously research + write + export a finished file")
    p_write.add_argument("--abstract", help="Topic/idea (prompted if omitted)")
    p_write.add_argument("--chapters", type=int, help="Number of chapters/sections")
    p_write.add_argument("--max-revisions", type=int)
    p_write.add_argument("--no-humanize", action="store_true",
                         help="Skip the humanizer pass that strips AI tells")

    p_run = sub.add_parser("run", parents=[common], help="Drive the pipeline until done or escalation")
    p_run.add_argument("--force", action="store_true", help="Proceed past a consolidation review")
    # Tri-state (default None): switch the project's run mode as it resumes. --autonomous
    # also unblocks an escalated unit so the run finishes without pausing.
    p_run.add_argument("--autonomous", dest="autonomous", action="store_const", const=True,
                       default=None, help="Stop pausing for review; commit best drafts and finish")
    p_run.add_argument("--manual", dest="autonomous", action="store_const", const=False,
                       help="Re-enable human-in-the-loop review at each chapter/section")
    sub.add_parser("status", parents=[common], help="Show run state + open reviews")

    p_rev = sub.add_parser("review", parents=[common], help="Answer an escalation")
    p_rev.add_argument("--chapter", type=int)
    p_rev.add_argument("--instruction")

    p_revise = sub.add_parser("revise", parents=[common],
                              help="Rewrite one committed chapter/section of a finished piece")
    p_revise.add_argument("--chapter", type=int, help="Chapter/section number to rewrite")
    p_revise.add_argument("--instruction", help="What to change, in your words")

    p_read = sub.add_parser("read", parents=[common], help="Print chapter/summary/manuscript")
    p_read.add_argument("--chapter", type=int)
    p_read.add_argument("--summary", action="store_true")
    p_read.add_argument("--manuscript", action="store_true")
    p_read.add_argument("--v", type=int, help="Read draft version K of the chapter (see `versions`)")

    p_versions = sub.add_parser("versions", parents=[common],
                                help="List draft snapshots (variants, revisions, finals)")
    p_versions.add_argument("--chapter", type=int, help="Only this chapter/section")

    sub.add_parser("brief", parents=[common], help="Show the goal: thesis, audience, length")

    p_tr = sub.add_parser("tableread", parents=[common],
                          help="Skeptical-reader pass over the finished piece")
    p_tr.add_argument("--as", dest="persona",
                      help='Read as a specific persona (e.g. "a CTO evaluating vendors")')

    sub.add_parser("eval", parents=[common],
                   help="Quality report: judged rubric + deterministic metrics")

    sub.add_parser("memory", parents=[common], help="Inspect canon + graph")
    sub.add_parser("produce", parents=[common], help="Run Production (front/back matter + assembly)")
    sub.add_parser("consolidate", parents=[common], help="Run a consolidation pass")
    sub.add_parser("skills", parents=[common], help="List learned skills + efficacy")
    sub.add_parser("config", parents=[common], help="Show model routing + settings")
    sub.add_parser("list", parents=[common], help="List books for the user")
    p_export = sub.add_parser("export", parents=[common],
                              help="Export the manuscript (pdf/epub/html/docx/txt/md, or all)")
    p_export.add_argument("formats", nargs="*",
                          help="Format(s): pdf epub html docx txt md, or 'all' "
                               "(omit to choose interactively)")
    p_export.add_argument("--format", default=None,
                          help="Output format(s), e.g. 'pdf' or 'all' (alternative to the positional)")

    p_polish = sub.add_parser("polish", parents=[common],
                              help="Re-fix an existing manuscript (references, citations, figures) - no LLM, then re-export")
    p_polish.add_argument("--format", default=None,
                          help="Formats to re-export (default: those already present, or 'all')")
    sub.add_parser("evidence", parents=[common],
                   help="Write evidence_report.md - thesis + influence-ranked sources (no LLM)")
    p_seo = sub.add_parser("seo", parents=[common],
                           help="Write seo_report.md - on-page audit + keyword/hashtag pack")
    p_seo.add_argument("--keyword", help="Pin the primary keyword (else inferred)")
    p_promote = sub.add_parser("promote", parents=[common],
                               help="Write promo/ - X thread, LinkedIn post, teaser, TL;DR + headlines")
    p_promote.add_argument("--to", help="Format(s), comma-separated: x-thread, linkedin, "
                                        "newsletter-teaser, tldr (default: all)")
    p_promote.add_argument("--keyword", help="Pin the primary keyword (else keywords.json / inferred)")
    p_web = sub.add_parser("web", parents=[common],
                           help="Local web dashboard: run pieces + evals/traces/cost in a browser")
    p_web.add_argument("--port", type=int, default=8787)
    p_web.add_argument("--no-browser", action="store_true", help="Don't auto-open the browser")
    sub.add_parser("seed-skills", parents=[common], help="Install built-in craft skills")
    p_del = sub.add_parser("delete", parents=[common], help="Permanently delete a book")
    p_del.add_argument("name", nargs="?", help="Book ID to delete (positional shorthand)")
    p_del.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    return ap


def _apply_provider(llm_mod, settings) -> None:
    """Select the model host from WRITINGAGENT_PROVIDER (if set) or settings.provider.

    An unknown id is a warning, not a crash - configure_provider leaves the default
    (OpenRouter) in place, so a typo never bricks startup."""
    import os
    choice = os.getenv("WRITINGAGENT_PROVIDER") or settings.provider
    try:
        llm_mod.configure_provider(choice)
        from .. import providers
        settings.provider = providers.resolve(choice)   # keep settings in sync so the
        #   banner / _stack_label / key-warning reflect the ACTUAL active provider
    except ValueError as e:
        print(f"warning: {e}", file=sys.stderr)
        if choice != settings.provider:
            try:
                llm_mod.configure_provider(settings.provider)
            except ValueError:
                pass


def main() -> None:
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        from dotenv import load_dotenv
        load_dotenv()                      # nearest .env from the CWD (dev checkouts)
        load_dotenv(brain.HOME / ".env")   # the agent home (written by /setkey); no override
    except ImportError:
        pass

    settings = load_settings()
    cfg = load_config()
    ui.apply_theme(settings.theme)   # before the shell import - it copies the palette
    from .. import llm as _llm
    _llm.configure_timeout(settings.request_timeout)
    _llm.configure_openrouter_providers(settings.openrouter_providers)
    _llm.configure_fallback(cfg.fallback)
    _apply_provider(_llm, settings)
    if len(sys.argv) == 1:  # bare `writing-agent` / `python writingagent.py` -> interactive shell (TUI)
        from ..shell import run_shell
        run_shell(build_parser(settings), _COMMANDS, cfg, settings)
        return
    args = build_parser(settings).parse_args()
    ui.set_plain(getattr(args, "plain", False))
    if not brain.is_safe_id(args.user):
        sys.exit(f"Invalid --user '{args.user}' (use letters, digits, - . _).")
    try:
        _COMMANDS[args.command](args, cfg, settings, args.user)
    except KeyboardInterrupt:
        sys.exit("\nInterrupted - progress is saved; run again to resume.")
    except Exception as e:  # noqa: BLE001 - map known failures to a next step
        # The shell already routes errors through explain_error (dispatch.py); the
        # one-shot CLI used to dump a raw traceback for the exact same bad-key case.
        hint = ui.explain_error(e)
        if hint:
            sys.exit(f"✗ {hint}")
        raise
