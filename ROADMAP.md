# Roadmap

Where Writing Agent is going. This is a direction, not a promise — priorities shift with
feedback. The authoritative spec is [`plan.md`](plan.md); this file is the short "what's next".

## Now / near-term
- **Publish to PyPI** so `pip install writing-agent` works (release automation is in place; needs
  the one-time PyPI trusted-publisher setup — see `.github/workflows/release.yml`).
- **Republish the `writingagent` npm launcher** once the package is on PyPI (the published launcher
  is stale vs. the local version).
- **Provider reach:** first-party **Anthropic**, **Perplexity**, **Cerebras**, **SambaNova**, and
  **AWS Bedrock / Azure OpenAI via gateway** all ship now (`providers.py`). No blessed default — the
  first-run wizard lets the writer choose a host.

## Next
- **Native AWS Bedrock transport** (boto3 + SigV4) as an optional `[bedrock]` extra, so Bedrock works
  without an OpenAI-compatible gateway in front of it. (Today it's reached via a gateway URL.)
- **Native Azure OpenAI** support (deployment + `api-version`) as a first-class client path.
- **Vision / multimodal input** — let a run take reference images (charts, diagrams, screenshots) as
  grounding, on the vision-capable models the provider layer already reaches.
- **Refactors carried over from the review sweep** (maintainability, not bugs): extract the
  near-identical `book.py`/`article.py` `_revise`/`_reoutline`/`_draft`/tool-runner blocks into
  `common.py`, and unify the legacy-vs-agentic consolidation-cadence state keys.

## Bigger bets (need real API spend / a human)
- **Independent blind A/B** vs. a strong single-prompt baseline, judged by a third model/human (n≥5).
- **Full 10+ chapter book validation** end-to-end at real-run volume.
- **Trained agentic policy** with enough trace-corpus volume for the learned controller to bite.

## Good first issues
Great places to start contributing (see [`CONTRIBUTING.md`](CONTRIBUTING.md)):
- Add a provider to `providers.py` (one registry entry) + its signup URL + `.env.example` line.
- Add a `register` profile (`registers.py`) or a public-domain `persona` (`personas.py`) with an
  original-pastiche exemplar.
- Add an export format or improve an existing exporter's fidelity (`export.py`).
- Broaden test coverage for an under-tested module (run `pytest --cov` to find gaps).
