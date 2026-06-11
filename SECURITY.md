# Security Policy

## Reporting a vulnerability

Please report security issues **privately** via GitHub's
[private vulnerability reporting](https://github.com/vikast908/WritingAgent/security/advisories/new)
(Security → Report a vulnerability), rather than opening a public issue.

We aim to acknowledge reports within a few days. Please include reproduction steps
and the affected version/commit.

## Scope & things to know

WRITING AGENT runs **locally** on Linux, macOS, and Windows, operated by the user on their
own machine. A few properties are worth understanding:

- **Secrets:** your `OPENROUTER_API_KEY` lives in `.env` (gitignored). Never commit it.
  The app reads it only to call OpenRouter.
- **LLM-driven command execution:** the TUI's conversational assistant can propose
  commands that run automatically. Destructive/config commands (`delete`, `/user`,
  `/set`) are **blocked** from auto-execution - the human must type them. Project/user
  ids are validated and deletes are confined to the brain directory.
- **Generated content:** manuscripts and SVG diagrams come from an LLM. Exported HTML is
  sanitized (script/iframe/event handlers stripped), but treat generated output as
  untrusted if you publish it.
- **Untrusted web content / prompt injection:** everything fetched from the public web
  (search snippets, deep-research page text) is fenced as **data-only** before entering any
  prompt - spoof-resistant markers plus a standing instruction that the block is never
  instructions. A hostile page cannot direct the writer, but no fence is perfect: review
  research-grounded output before publishing.
- **Network:** the only outbound calls are to your configured OpenRouter endpoint, the
  optional DuckDuckGo researcher (plus full page fetches when `deep_research` is enabled),
  and optional Wikimedia Commons image search. All manuscript data stays on disk locally.
- **Telemetry stays local:** per-call usage records (model, tokens, cost, latency) are
  written only to `.index/telemetry/` on your machine - nothing is sent anywhere.
- **Cost containment:** `max_run_tokens` caps a run's total token spend; the run pauses
  cleanly at the cap and is resumable.

## Supported versions

This is pre-1.0 software; security fixes land on `master` and in the latest release.
