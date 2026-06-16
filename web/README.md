---
title: Writing Agent
emoji: ✍️
colorFrom: indigo
colorTo: purple
sdk: gradio
app_file: app.py
pinned: false
license: mit
---

# Writing Agent — zero-install web demo

A browser front-end over the Writing Agent pipeline, so anyone can try it without a
terminal, a Python install, or an API key. It lowers the single biggest adoption barrier
in `PRD.md`: "you must be comfortable with a CLI and your own key."

## What it does

- **Topic in → finished piece out**, with the whole pipeline visible: plan → draft
  variants → critique → verify cited claims → strip AI tells → assemble.
- **Free preview (default).** No key. Runs in fake mode (`WRITINGAGENT_FAKE=1`) so a
  visitor sees the *shape* of a real run at zero cost. Great for "what does this thing
  even do?" without a signup wall.
- **Real run (bring your own key).** Toggle it on, pick a provider, paste your key, and
  it produces a genuine article/book — and the **evidence report** (sources ranked by
  influence *and* credibility) actually populates.

The underlying engine also supports an optional self-directing (agentic) mode — off by
default and not exposed in this demo.

## Run it locally

```bash
pip install -e ".[web]"     # from the repo root
python web/app.py           # open the printed http://127.0.0.1:7860
```

## Deploy as a Hugging Face Space

1. Create a new **Gradio** Space.
2. Upload this folder's `app.py`, `requirements.txt`, and this `README.md` (its YAML
   front-matter configures the Space — `sdk: gradio`, `app_file: app.py`).
3. The Space builds and serves the demo. Free preview works out of the box; visitors who
   want a real run paste their own key (nothing is stored — the key lives only for that
   request's process env).

## Notes

- The package never imports Gradio; only `app.py` does, lazily. The demo talks only to
  the **public** `Agent`/`Project` facade (`writingagent.api`), so it stays stable across
  releases.
- `configure_runtime()` mutates process-global env (the provider key), so a public
  deployment should run **single-worker** (the Gradio default) or serialize runs.
- For a public, key-less deployment you control, set a server-side key in the Space
  secrets and adapt `configure_runtime()` to read it — but rate-limit first.
