"""Durable on-disk state machine (plan.md §6) - package facade.

The brain on disk IS the checkpoint: every step persists to run_state.json + committed
markdown, so `run()` is resumable across process restarts and human pauses. (This fulfils
the plan's checkpoint/resume requirement without LangGraph's in-memory interrupt machinery;
LangGraph can wrap this engine later - see plan §12 note.)

Phases: chapters -> consolidate -> production -> learn -> done.
Per chapter: write -> critique -> (approve→commit | revise<cap→rewrite | cap/escalate→ESCALATE).

This was one ~2.3k-line module; it's split into seams for readability and re-exported
here so `orchestrator.X` resolves exactly as before (callers and tests are unchanged):

  common   shared leaf helpers - research, draft selection (_pick_variant /
           _divergent_first_draft), claim verification, citation/reference utils,
           run-state scaffolding, the learner tail - used by both pipelines
  book     the chapter pipeline + run() (the public entry; also dispatches articles)
  article  the section pipeline
  export   pdf/epub/html/docx/txt/md, repolish_manuscript, build_evidence_report
  manage   lifecycle/state - delete, status, record_instruction, apply_autonomous
  review   approve_escalation, revise_unit, run_table_read, evaluate_project

Dependency direction (acyclic): common <- {article, book, manage}; article <- export;
book <- {article, manage}; review <- {book, article, common}.
"""
from __future__ import annotations

from .article import *  # noqa: F401,F403
from .book import *  # noqa: F401,F403
from .common import *  # noqa: F401,F403
from .export import *  # noqa: F401,F403
from .manage import *  # noqa: F401,F403
from .review import *  # noqa: F401,F403
