# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open-source scaffolding: `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, issue/PR templates, GitHub Actions CI (Linux/macOS/Windows
  × Python 3.10–3.13), ruff config, and pre-commit hooks.
- Live `run` dashboard (elapsed time, live token count, stage, event log).
- Argument/value autocomplete and persistent shell history in the TUI.
- Rich `status` (phase stepper + word count + reading time), Markdown-rendered
  `read`/`memory`, and skill efficacy bars.
- Token-usage telemetry, on-disk caching for web search + SVG diagrams, and a
  `--plain` / `NO_COLOR` mode.
- Per-request `request_timeout` setting.

### Changed
- Hardened LLM calls: classified retry with exponential backoff, fail-fast on 4xx,
  request timeout, and a real structured-output repair retry.
- Atomic, resumable on-disk state; durable against crashes mid-run.
- `pyproject.toml` is now the canonical dependency source; packaging metadata
  completed (license, authors, URLs, classifiers, `dev`/`headroom` extras).

### Security
- The conversational assistant can no longer auto-execute `delete` / `/user` /
  `/set`; project/user ids are validated and deletes are confined to the brain dir.
- Exported HTML is sanitized (script/iframe/event handlers stripped).

### Removed
- Dead vertical-slice prototype (`run.py`, `src/book_agent/slice.py`).

## [0.1.0]
- Initial book + article pipelines: plan → write → critique → revise → humanise →
  commit, with canon/consolidation, learned craft skills, and six export formats.
