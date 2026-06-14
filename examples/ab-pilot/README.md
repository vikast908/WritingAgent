# A/B pilot — Writing Agent outputs

These are the **unedited Writing Agent articles** generated for the blind A/B pilot
(`benchmarks/blind_ab/`, v0.2.0 · `deepseek-v4-pro` · `units=4` · researcher on). They're here as
real, judge-it-yourself output. Only the *Writing Agent* side is included — the competitor (Claude)
side was part of the test, not the product, so it lives only in the (gitignored) run dir.

| Article | Prompt |
|---|---|
| [vector-databases.md](vector-databases.md) | How vector databases actually work |
| [ab-tests-underpowered.md](ab-tests-underpowered.md) | Why most A/B tests are underpowered, and what to do about it |
| [microservices-small-teams.md](microservices-small-teams.md) | The real reason microservices slow small teams down |

Each makes a defended thesis and carries 15–20 inline-researched sources (see the References list at
the end of each). The pilot's scoring + the honest caveats are in
[`benchmarks/blind_ab/RESULTS.md`](../../benchmarks/blind_ab/RESULTS.md) — headline: Writing Agent
won on sourcing/completeness, the Claude side won on concision, and the run was self-judged so it's
**indicative, not independent**. Known rough edges visible in these very files: some thesis
repetition, and (in the A/B-tests piece) one stray `[N]` citation marker.
