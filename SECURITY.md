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

- **Secrets:** your model-host API key lives in `.env` (gitignored) - whichever host you
  pick (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, … - any of the 23 in
  `providers.py`). Never commit it. The app reads it only to call that configured host.
- **LLM-driven command execution:** the TUI's conversational assistant can propose and
  auto-run commands - including `/set`, so plain-English config changes ("turn on the
  researcher", "use the poe-gothic persona") take effect. Config is reversible and every
  line the assistant runs is echoed back. Only two commands stay **fenced** from
  auto-execution - the human must type them: `delete` (irreversible data loss) and `/user`
  (switches tenant/identity). Project/user ids are validated and deletes are confined to
  the brain directory.
- **Generated content:** manuscripts and SVG diagrams come from an LLM. Exported HTML is
  sanitized (script/iframe/event handlers stripped), but treat generated output as
  untrusted if you publish it.
- **Untrusted web content / prompt injection:** everything fetched from the public web
  (search snippets, deep-research page text) is fenced as **data-only** before entering any
  prompt - spoof-resistant markers plus a standing instruction that the block is never
  instructions. A hostile page cannot direct the writer, but no fence is perfect: review
  research-grounded output before publishing.
- **Network:** the only outbound calls are to (1) your **configured model host** (any of the
  23 in `providers.py` - the one you pick); (2) **DuckDuckGo** for keyless web search, plus
  full page fetches from arbitrary web hosts when `deep_research` is enabled (SSRF-guarded,
  robots-respecting); (3) **Wikimedia Commons** image search for illustrated content; (4) the
  optional **Firecrawl** search/scrape backend, only when you opt in with `FIRECRAWL_API_KEY`
  set (`search_provider: firecrawl`); and (5) **mermaid.ink**, used only during export to
  render Mermaid diagrams to PNG. All manuscript data stays on disk locally.
- **Telemetry stays local:** per-call usage records (model, tokens, cost, latency) are
  written only to `.index/telemetry/` on your machine - nothing is sent anywhere.
- **Cost containment:** `max_run_tokens` caps a run's total token spend; the run pauses
  cleanly at the cap and is resumable.

## Supported versions

This is pre-1.0 software; security fixes land on `master` and in the latest release.
