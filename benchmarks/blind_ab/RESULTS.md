# Blind A/B results

- **Date:** 2026-06-14
- **Writing Agent:** v0.2.0, `deepseek-v4-pro`, `units=4`, researcher on
- **Competitor:** Claude (written directly, "write a long-form article with sources" style)
- **Scorer:** Claude (the assistant) - **see the integrity caveat below; this is a pilot, not proof**
- **Prompts:** 3 (`prompts.txt`)

## ⚠️ Integrity caveat (read first)
This run is **not an independent result.** The same model (Claude) **wrote the competitor side AND
judged**, and despite anonymization + tell-stripping the judge could recognize the sides (Writing
Agent's research depth is distinctive). So bias runs in *both* directions (toward flattering the
product, and toward flattering the judge's own prose). Treat the numbers as **indicative**. The credible
version needs a human, or a *third* model that wrote neither side, to score the anonymized `A.md`/`B.md`.

## Headline

- **Writing Agent win-rate (excl. ties):** 100% (2/2)
- **Raw:** Writing Agent **2** · Claude **0** · ties **1**
- **Avg insight / trust / readability** - Writing Agent: **4.3 / 4.7 / 4.0** · Claude: **4.7 / 3.7 / 5.0**

The win count flatters Writing Agent; the **dimension scores are the honest signal**: Writing Agent
wins decisively on **sourcing/trust**, Claude wins on **readability/concision**, and **insight is
roughly even** (Claude slightly ahead).

## Per-case

| Prompt | Winner | Why |
|---|---|---|
| How vector databases actually work | **Writing Agent** | Defended a real thesis ("the cosine-vs-Euclidean debate is a distraction; HNSW params + quantization dominate"), worked math + code + a monitoring checklist, **20 cited sources**. Claude's was tighter and very readable but far thinner on sourcing. |
| Why most A/B tests are underpowered | **Writing Agent** (close) | More complete + **20 sources** + worked examples + a sample-size-calculator walkthrough (false negatives *and* the winner's curse / Type-M). Claude's was sharper and more advanced (CUPED, sequential, non-inferiority) but ~4 sources. A reasonable judge could call this a tie. |
| The real reason microservices slow small teams | **tie** | Claude's thesis was more on-prompt and honest (boundary economics + Conway's law); Writing Agent's was more thorough (code, Segment/Basecamp cases) but leaned on a cynical "resume-driven development" angle and padded its source list with resume-template pages. |

## What Writing Agent won on
- **Sourcing depth** - 15–20 real, specific, linked sources per piece vs ~3–5 for Claude. This is the
  product's stated edge, and it showed.
- **Completeness** - worked examples, code, checklists, concrete numbers. The pieces read as finished,
  publishable articles, not just answers.
- **A defended thesis** - each piece took and argued a position (the anti-slop machinery working).

## Where it lost / threats to validity
- **Repetition / length** - WA pieces are long and hammer their thesis (telescope/shrimp-net,
  "resume/complexity tax"); a critic's "no repeated talking points" would fire. Claude's were tighter.
- **A stray `[N]`** survived into the A/B-tests piece (a citation the pipeline didn't number).
- **Citation quality** - the microservices piece padded its 20 sources with resume-template SEO pages
  to support its "resume-driven" angle. Volume ≠ authority.
- **Bias** - same model wrote-and-judged (see caveat). And n=3.

## Decision
Indicative support for the README claim **on sourcing and completeness**, *not* on readability. Next:
re-run with an **independent judge** (human or third model) and more prompts; and feed the defects
above (repetition, stray `[N]`, low-quality citations) back into the prompts/critic.
