"""Zero-install web demo for the Writing Agent (plan §15: lower the terminal barrier).

A small Gradio front-end over the public ``Agent``/``Project`` facade. A visitor types
a topic, watches the pipeline run live, and reads the finished piece *plus its evidence
report* - the "show, don't tell" of the "argues a thesis, cites real sources" claim.

Two ways to run:

* **Free preview (default).** No API key. Sets ``WRITINGAGENT_FAKE=1`` so the whole
  pipeline runs offline with placeholder model output - the visitor sees the *shape* of
  a real run (planning -> drafting -> critique -> verify -> humanize -> assemble) with
  zero cost and zero setup.
* **Real run (bring your own key).** The visitor pastes their own provider API key; the
  demo routes the run through that provider and produces a genuine article/book.

Deploy as a Hugging Face Space (``sdk: gradio``, ``app_file: app.py``) - see
``web/README.md``. The package itself never imports gradio; only this file does, and it
imports it lazily so the helpers below stay unit-testable without the dependency.

Run locally::

    pip install -e ".[web]"
    python web/app.py            # then open the printed http://127.0.0.1:7860
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
from pathlib import Path

# Make `import writingagent` resolve to the in-repo source when running from a checkout
# (no install needed); on a Hugging Face Space the installed package is used instead.
_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from writingagent import Agent  # noqa: E402

# Curated provider menu for the demo. Each maps the visitor-facing label to the
# provider id the pipeline knows and the env var that carries its key. (The full
# provider registry lives in writingagent.providers; this is a friendly subset.)
PROVIDERS: dict[str, dict[str, str]] = {
    "OpenRouter": {"id": "openrouter", "env": "OPENROUTER_API_KEY"},
    "DeepSeek": {"id": "deepseek", "env": "DEEPSEEK_API_KEY"},
    "OpenAI": {"id": "openai", "env": "OPENAI_API_KEY"},
    "Gemini": {"id": "gemini", "env": "GEMINI_API_KEY"},
}

# Keep the free preview cheap and snappy: small pieces, researcher off (fake mode has
# no real web anyway), humanizer on so the AI-tell stripping is visible.
MAX_UNITS = 8


def configure_runtime(real_run: bool, provider: str, api_key: str) -> str:
    """Set the process env for this run and return the provider id to route through.

    Free preview forces fake mode (no key, no network). A real run clears fake mode,
    installs the visitor's key on the right env var, and selects the provider. Returns
    the provider id ('' in fake mode). Raises ValueError if a real run has no key.

    NB: this mutates process-global env, so a public deployment should run single-worker
    (the default for a Gradio Space) or serialize runs.
    """
    if not real_run:
        os.environ["WRITINGAGENT_FAKE"] = "1"
        return ""
    key = (api_key or "").strip()
    if not key:
        raise ValueError("A real run needs an API key - paste one, or use the free preview.")
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(f"Unknown provider {provider!r}.")
    os.environ.pop("WRITINGAGENT_FAKE", None)
    os.environ[spec["env"]] = key
    os.environ["WRITINGAGENT_PROVIDER"] = spec["id"]
    return spec["id"]


def generate(topic: str, mode: str, units: int, provider: str, api_key: str, real_run: bool):
    """Drive one run, streaming (log, manuscript, evidence_report, download_path).

    A generator so the UI can show progress live: the pipeline runs in a worker thread
    and its progress lines are streamed out as they arrive; the finished manuscript,
    evidence report, and a downloadable markdown file are yielded at the end.
    """
    topic = (topic or "").strip()
    if not topic:
        yield "Enter a topic to begin.", "", "", None
        return
    units = max(1, min(int(units or 4), MAX_UNITS))
    try:
        provider_id = configure_runtime(real_run, provider, api_key)
    except ValueError as exc:
        yield f"⚠️ {exc}", "", "", None
        return

    log_q: queue.Queue = queue.Queue()
    done = object()
    out: dict = {}

    def worker() -> None:
        try:
            kwargs = {"user": "demo", "autonomous": True, "mode": mode, "use_researcher": False}
            if provider_id:
                kwargs["provider"] = provider_id
            agent = Agent(**kwargs)
            project = agent.create(topic, mode=mode, units=units)
            project.run(progress=lambda line: log_q.put(str(line)))
            out["manuscript"] = project.read(manuscript=True)
            out["evidence"] = project.evidence_report() if mode == "article" else ""
            out["download"] = str(project.export("md"))
        except Exception as exc:  # noqa: BLE001 - surface any failure to the visitor
            out["error"] = exc
            out["trace"] = traceback.format_exc()
        finally:
            log_q.put(done)

    threading.Thread(target=worker, daemon=True).start()

    banner = ("🧪 Free preview (placeholder model output - no key, no cost)\n"
              if not real_run else f"🔑 Real run via {provider}\n")
    lines: list[str] = [banner]
    while True:
        item = log_q.get()
        if item is done:
            break
        lines.append(item)
        yield "\n".join(lines[-60:]), "", "", None

    if "error" in out:
        lines.append(f"\n❌ Run failed: {out['error']}")
        yield "\n".join(lines[-60:]), "", "", None
        return

    evidence = out.get("evidence") or (
        "*The evidence report ranks real cited sources by influence and credibility. "
        "In the free preview there are no real sources - try a real run with your own key "
        "to see it populated.*" if mode == "article"
        else "*The evidence report is generated for articles.*")
    lines.append("\n✅ Done.")
    yield "\n".join(lines[-60:]), out.get("manuscript", ""), evidence, out.get("download")


INTRO = """\
# ✍️ Writing Agent — try it in your browser

The autonomous long-form writer that **argues a thesis and cites real sources** — not slop.
It plans, drafts several variants, critiques and revises its own work, verifies cited claims
against their sources, strips AI tells, and ships a finished piece with a shareable
**evidence report**.

Type a topic and hit **Write**. The *free preview* runs the whole pipeline offline with
placeholder text (no key, no cost) so you can see the shape of a run. For a real piece,
switch on **Real run** and paste your own API key.
"""


def build_ui():
    """Construct the Gradio Blocks app (imports gradio lazily so the helpers above stay
    importable/testable without the optional dependency)."""
    import gradio as gr

    with gr.Blocks(title="Writing Agent", theme=gr.themes.Soft()) as demo:
        gr.Markdown(INTRO)
        with gr.Row():
            with gr.Column(scale=2):
                topic = gr.Textbox(label="Topic", placeholder="How vector databases actually work",
                                   lines=2)
                with gr.Row():
                    mode = gr.Radio(["article", "book"], value="article", label="Mode")
                    units = gr.Slider(1, MAX_UNITS, value=4, step=1,
                                      label="Sections / chapters")
                real_run = gr.Checkbox(value=False,
                                       label="Real run (bring your own API key)")
                with gr.Group(visible=False) as key_group:
                    provider = gr.Dropdown(list(PROVIDERS), value="OpenRouter", label="Provider")
                    api_key = gr.Textbox(label="API key", type="password",
                                         placeholder="sk-... (kept only for this run)")
                real_run.change(lambda v: gr.update(visible=v), real_run, key_group)
                go = gr.Button("✍️ Write", variant="primary")
            with gr.Column(scale=3):
                log = gr.Textbox(label="Live progress", lines=14, max_lines=14,
                                 show_copy_button=True)
                download = gr.File(label="Download (.md)")
        with gr.Tabs():
            with gr.Tab("Manuscript"):
                manuscript = gr.Markdown()
            with gr.Tab("Evidence report"):
                evidence = gr.Markdown()

        go.click(generate, [topic, mode, units, provider, api_key, real_run],
                 [log, manuscript, evidence, download])
    return demo


if __name__ == "__main__":
    build_ui().launch()
