# Blind A/B — Writing Agent vs ChatGPT/Claude

The single most important thing to validate (PRD §9): **does the output actually beat just prompting
ChatGPT/Claude on blind reads?** This kit runs that test honestly — same prompts, anonymized sides,
score *before* you reveal which tool wrote which.

## The 5-step flow

```bash
# 1. Generate Writing Agent's side for every prompt  (real run; ~$0.25/prompt)
python benchmarks/blind_ab/generate.py

# 2. By hand: paste ChatGPT/Claude's reply to each prompt into
#    benchmarks/blind_ab/cases/<slug>/chatgpt.md   (the prompt is in that folder's prompt.txt)

# 3. Anonymize into A.md / B.md + a hidden key + a score sheet
python benchmarks/blind_ab/blind.py

# 4. By hand: read each case's A.md and B.md and fill score_sheet.md  (winner: A/B/tie; see SCORING.md)
#    Do NOT open writingagent.md / chatgpt.md until you're done.

# 5. Reveal + tally the win-rate
python benchmarks/blind_ab/tally.py
```

Then paste the summary into [`RESULTS.md`](RESULTS.md) and commit it — that's the proof the README's
claim rests on.

## Why each step

- **Anonymized A/B** (`blind.py`) randomizes which tool is A vs B per case and hides the mapping in
  `.blind_key.json`, so your scoring can't be biased by knowing the source. It also strips the few
  Writing-Agent format tells (read-time header, the influence-score prefix on references) so you judge
  substance, not the brand.
- **Score before reveal.** `tally.py` is the only thing that un-blinds.

## Notes & honesty caveats

- **Cost:** `generate.py` makes real LLM calls. Use a small prompt set first. (Set `WRITINGAGENT_FAKE=1`
  to dry-run the *wiring* with placeholder text — useful to test the flow, useless for judging quality.)
- **Fairness:** keep the competitor prompt identical to `prompt.txt`, and give ChatGPT/Claude a fair
  shot (a normal "write a long-form article on X with sources" prompt). Document exactly what you
  pasted in RESULTS.md.
- **Blinding isn't perfect** — writing *style* can still hint at the source. Judge the page on its
  merits; that's the spirit of SCORING.md.
- **`cases/`, `score_sheet.md`, and `.blind_key.json` are gitignored** (run-local). Commit only the
  final numbers in `RESULTS.md`.
