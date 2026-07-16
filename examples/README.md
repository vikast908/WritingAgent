# Examples - real output from Writing Agent

Don't take the README's word for it. These are **actual, unedited pieces the system generated** - so
you can judge the output before you install anything.

## 📄 Article - *Your Voice Assistant's 100ms Problem*

A long-form technical article with a real thesis, inline-researched sources, and self-laid-out
diagrams. Generated end-to-end, then the references/citations cleaned deterministically.

- [**`voicebot-article/manuscript.md`**](voicebot-article/manuscript.md) - the finished piece (~16 min read, 6 sections, built-in SVG figures)
- [**`voicebot-article/evidence_report.md`**](voicebot-article/evidence_report.md) - the receipts: the thesis it argues + **46 sources ranked by influence (0–100)**

> This is the headline differentiator made visible: the article takes a contestable position, and the
> evidence report shows exactly which sources carried it. Most AI writing can't show you either.

## 🅰️🅱️ A/B pilot - three more articles, benchmarked

Three Writing Agent articles from the blind A/B pilot (vs Claude), in
[**`ab-pilot/`**](ab-pilot/) - vector databases, underpowered A/B tests, and microservices for small
teams. The scoring + honest caveats are in [`../benchmarks/blind_ab/RESULTS.md`](../benchmarks/blind_ab/RESULTS.md).

## 📚 Book - *The Misprint File*

A full short novel (3 chapters) with canon/continuity tracking and front/back matter, in
[**`../SampleRun/`**](../SampleRun/) - manuscript, per-chapter files, the canon (characters,
timeline, world rules), and the learned craft skills the run produced.

## Generate your own (≈$0.25, a couple of minutes)

```bash
writingagent write "How vector databases actually work"
# → researches, drafts, self-critiques, fact-checks, humanises, exports a finished file
#   + an evidence_report.md next to it
```

Zero-install try: open [`colab_quickstart.ipynb`](colab_quickstart.ipynb) in Google Colab and run it
(you'll need a free [OpenRouter](https://openrouter.ai/) key). Or run locally in **fake mode** (no key,
placeholder output) to see the whole flow for free:

```bash
WRITINGAGENT_FAKE=1 writingagent new --abstract "test" --pick 1 && writingagent run
```

## Contribute a sample

Generated something good? PRs welcome - add a folder here with the `manuscript.md` (and its
`evidence_report.md` for articles), plus a one-line note on the topic and settings used. Real,
diverse examples are the best advertisement the project has.
