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
  `/set`) are **blocked** from auto-execution — the human must type them. Project/user
  ids are validated and deletes are confined to the brain directory.
- **Generated content:** manuscripts and SVG diagrams come from an LLM. Exported HTML is
  sanitized (script/iframe/event handlers stripped), but treat generated output as
  untrusted if you publish it.
- **Network:** the only outbound calls are to your configured OpenRouter endpoint, the
  optional DuckDuckGo researcher, and optional Wikimedia Commons image search. All
  manuscript data stays on disk locally.

## Supported versions

This is pre-1.0 software; security fixes land on `master` and in the latest release.
