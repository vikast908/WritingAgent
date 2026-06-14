# The Silent Experiment Killer: Why Your A/B Tests Fail Before They Even Start

*A beginner-friendly guide explaining the concept of statistical power for marketers and product managers, avoiding complex formulas and instead using visual metaphors (like telescopes and fishing nets) to show why small sample sizes lead to random, unreliable results.*

**Estimated read time:** 13 min  

---


---

## The Telescope with a Broken Lens: Why Your Dashboard's 'No Winner' Result Is a Lie

You close a two-week A/B test. The variant button copy felt promising, but the dashboard flashes "No statistically significant difference." You file the result, discard the idea, and move on. The problem is that the dashboard's verdict might be wrong, not because the math is broken, but because the experiment was designed to fail before it ever started.

Look at a distant star through a cheap plastic telescope. You see blackness, so you conclude no star is there. A professional astronomer using a proper instrument sees the star clearly. Did the star appear only when the better lens looked? No. It was always there, but the limited equipment could not resolve it. A/B tests behave the same way. When you run a test on a tiny sample, you peer through a toy telescope. The star, a real lift in conversion rate, could be directly in front of you, yet your instrument is too weak to detect it.

Statistical power is the probability your test will spot a genuine effect when one exists. If power is low, you are nearly guaranteed to miss real winners because random noise overwhelms the signal. This mistake, a false negative, shows up constantly in tests that skip a pre-test power check. Netflix's tech blog defines a false negative as a failure to detect a true effect, even when that effect is present. The accepted standard for a trustworthy experiment is 80% power: you accept a 20% chance of failing to see a real improvement. Yet many business tests never approach that threshold. When power is lacking, a "no winner" outcome is not evidence of a dud idea. It is evidence of a broken measurement setup.

The significance indicators built into most A/B tools do not solve this problem. They check whether the observed data would be unlikely under the null hypothesis, given the sample you happened to collect. They do not check whether that sample was large enough to give the test a fair shot at rejecting the null when a real improvement exists. It is like declaring a telescope functional because it shows a bright star while ignoring that its lens is so smudged it misses every dimmer object.

Suppose you test a redesigned landing page. Your baseline conversion rate is 2%, and you want to detect a 0.5 percentage point lift, a 25% relative increase. With only 5,000 visitors per variant, your test might have power so low that even if the redesign truly works, you would call "no winner" most of the time. The dashboard is not lying about the p-value, but it is lying by omission. It never warned you the experiment was a coin flip all along.

This failure to see what is actually there turns many A/B tests into random-noise generators. But the broken telescope creates another dangerous illusion: on rare occasions, a tiny lens can luck into a glimpse of a star and produce a dramatic "winner" that is just as misleading. That trap is where we turn next.

---

## Fishing with a Shrimp Net: How Small Sample Sizes Turn Winners into Ghosts

The previous section showed that an underpowered A/B test acts like a telescope with a smudged lens; it sees only noise and misses the real signal. That explains why "no winner" verdicts are so often deceptive. But why do so many tests become underpowered before the first visitor even arrives? The answer lives in sample size, and the clearest way to see it is to set aside the telescope and pick up a fishing net.

Walk up to a lake holding a shrimp net. The mesh is wide, the opening barely broader than your hand. Your goal is to catch a salmon. You drag the net through the water, pull it up, and find nothing. You would not announce the lake is empty. You would fault the gear. A shrimp net cannot land a salmon even if the lake is teeming with them.

An A/B test with too few visitors works the same way. The salmon is a genuine improvement in conversion rate: a sharper headline, a simpler checkout flow, a hero image that actually lifts sales. The shrimp net is a sample so thin that random noise overwhelms any real signal. The dashboard's "no statistically significant difference" verdict is not a finding of no effect; it is merely a report that your net came up empty. A tiny sample does not prove the idea was bad. It makes real winners invisible.

The concept that ties net to catch is the Minimum Detectable Effect, or MDE. The MDE is the smallest true difference in conversion rate a test has a high chance of spotting, given the number of visitors you collect. It acts as a sensitivity threshold, the mesh size of your statistical net. If the true effect is smaller than the MDE, the test cannot reliably detect it. A small sample forces a large MDE. You might be able to detect a 50% lift, but a 10% lift, hugely valuable in practice, slips right through the holes. A finer mesh, the kind a larger sample affords, detects smaller effects; a smaller MDE demands a far larger sample. That is not measurement. That is hope dressed up as math.

This is exactly what happens when a testing platform's built-in sample-size recommendation ignores your actual conversion rate and the lift you care about. It hands you a shrimp net and reports the result as if it were scientific. A common mistake is to set an unrealistically small MDE without checking the visitor volume it demands. A baseline conversion of 2% means the absolute movement you are hunting is barely a fraction of a percentage point. Detecting an effect that faint requires a visitor count far beyond what most sites gather in weeks or even months. Launching a test without pausing to check that gap turns an experiment into a lottery. You are no longer measuring; you are just hoping the net snags something by accident.

Noise makes the situation worse. Every test rides on a current of random variation: the day of the week, a competing promotion, a flicker in ad traffic. With a large sample, that noise averages out and the true signal, if there is one, rises above it. With a small sample, the noise stays as loud as the signal. The test becomes a blind draw, and a genuinely effective idea sinks without a trace.

The frustration of the shrimp-net test is that it burns time and traffic that could have powered a properly sized experiment. A product manager waits two weeks for a verdict, gets "no winner," and shelves a change that may well be the one that moves the needle. The platform's dashboard, by never asking what effect you needed to see, guaranteed that waste. All it did was confirm the obvious: the net was too coarse to hold anything worth keeping.

---

## The 'Winner' Illusion: Low Power and the Trap of Exaggerated Results

Your A/B test wraps up. The dashboard flashes green: "Variant B is a statistically significant winner with a +35% lift in conversion." You celebrate. The team begins planning the full rollout. Two months later, the lift shrinks to 2%, and the p-value drifts past 0.3. The "winner" was a ghost.

This is the winner's curse: an underpowered test that stumbles across a significant result will almost certainly overstate the true effect, sometimes dramatically. It is the mirror image of the false negative from earlier sections, and it is far more dangerous because it triggers action.

### How a Small Sample Manufactures a Giant "Winner"

The mechanism is straightforward. In a low-power test, the sample is too small to average out random noise. The true effect, if it exists, is buried in that noise. For the test to clear the p < 0.05 bar, the noise must push the observed conversion rate far above the true value. Only the luckiest upward fluctuations make the cut. The result is a headline lift that is mostly noise, not signal.

The fishing net metaphor from Section 2 captures this precisely: a shrimp net dragged through a lake rarely catches a salmon, but when it does, the fish appears enormous because the net itself is tiny. The measurement tool distorts the object it measures. The same is true of A/B tests run on platform defaults. Most testing tools set default parameters (often 80% power, 5% significance) but leave the minimum detectable effect unspecified, which means the sample-size recommendation is calculated from whatever traffic you happen to have rather than from the effect size you need to measure. If your traffic is low, the platform quietly accepts an MDE so large that only a grossly inflated result will ever cross the significance threshold. The tool never warns you that the test it just recommended is structurally cursed.

Researchers call this a Type M error: the sign of the effect is correct (the variant truly is better), but the magnitude is wildly wrong. The concept comes from Gelman and Carlin's work on exaggerated effect sizes in underpowered studies. In experiments with 20% power, the exaggeration ratio (observed effect divided by true effect) can be staggering. A test designed with power that low might report a 50% lift when it happens to cross the significance threshold. The number on the dashboard is not an estimate; it is a lottery ticket that happened to win.

### The Business Cost of Believing a Fluke

Etsy's data science team documented this pattern and built a James-Stein shrinkage estimator to correct for inflated effect sizes in their A/B tests. Without that correction, the team would have shipped features based on exaggerated numbers, wasting engineering effort and eroding trust in experimentation.

The business cost is concrete. A product manager sees a +40% lift on a checkout button color change, convinces leadership to prioritize the rollout, and allocates a sprint to it. When the change reaches the full user base, the lift disappears. The team has spent weeks on a phantom. Worse, the false positive poisons the well: stakeholders begin to doubt every test result, even the properly powered ones. The winner's curse is not a statistical curiosity; it directly damages the credibility of an experimentation program.

A common objection arises: "But the dashboard flagged it as significant. Doesn't that mean the sample was large enough?" No. Statistical significance is a post-hoc filter that checks whether the observed difference is unlikely under the null hypothesis, given the collected sample. It does not ask whether the test had enough power to detect a realistic effect size before the experiment started. A p-value from a tiny, noisy sample is like a magnifying glass that makes a speck of dust look like a boulder. The tool's green badge is blind to the fact that its own default settings let you launch a test destined to hallucinate.

When power is low, both the "no winner" verdict and the "big winner" verdict are untrustworthy. The telescope with the smudged lens will miss most planets, and the few it does see will appear grotesquely oversized. The only escape is to set the sample size based on the smallest effect you would find meaningful, before you launch the test. That calculation, and how to make it without a statistics degree, is what we turn to next.

---

## A Better Approach: Plugging Your Real-World Numbers into a Duration Calculator

Here is the uncomfortable truth most A/B testing platforms will not volunteer: their dashboard significance indicators answer the wrong question. They ask, "Given the data we collected, is the difference unlikely to be zero?" The question you actually need answered is, "Did we collect enough data to see the difference that matters to our business?" Those are not the same thing. A test can return "statistically significant" while being a coin flip, or "not significant" while having never stood a chance. The fix is not more statistics knowledge. It is running a single calculation before you launch.

### The Three Numbers That Actually Matter

Every experiment design starts with three inputs, and none of them require a statistics degree. You already know two of them.

**Baseline conversion rate.** What percentage of users currently take the action you care about? If 3% of landing page visitors click "Start Trial," that is your baseline. If you do not know this number, pull it from analytics for the past 30 days on the specific page or funnel step you intend to change. Do not guess. A wrong baseline cascades into a wrong required sample size.

**Minimum Detectable Effect (MDE).** This is the smallest lift you would consider worth shipping. Not the lift you hope for, the smallest one that would justify the engineering time, design effort, and opportunity cost of building the variant. If improving click-through from 3% to 3.15% (a 5% relative lift) would not change any downstream decision, then 5% is not your MDE. If you need a 15% relative lift to meaningfully move revenue, that is your MDE. Setting this honestly is where most teams trip. Marketing blog posts often suggest detecting a 10% lift. But if your baseline is 2% and traffic is modest, detecting a 10% relative lift (0.2 percentage points) requires sample sizes that may exceed your monthly traffic. That is not a failure of statistics; it is physics. The effect is simply too small for your telescope.

**Statistical power.** The convention is 80%. This means you accept a 20% chance of a false negative: missing a real effect that is at least as large as your MDE. You can choose 90% power if the cost of missing a winner is high, but that increases the required sample size. For most product and marketing tests, 80% is the pragmatic default.

Armed with these three numbers, you do not solve equations. You open a calculator.

### The Calculator That Short-Circuits Guesswork

Evan Miller's sample size calculator (linked in virtually every practitioner's guide to A/B testing) [N] is the tool that transforms the preceding three inputs into one output: the number of users you need per variant. You enter your baseline conversion rate, your MDE as a relative percentage, and your desired power. The calculator returns a sample size.

Concrete example: baseline conversion 3%, desired MDE 10% relative lift (so 3.3% conversion for the variant), 80% power. The calculator says you need roughly 11,000 users per variant. If your daily traffic to that page is 500 visitors, you need 44 days for a two-variant test. If your traffic is 5,000 visitors per day, you need about four and a half days.

Notice what changed: nothing about the statistical method. What changed was acknowledging reality before the test began. You now know that with 500 daily visitors, testing for a 10% lift is a multi-month commitment, not a two-week sprint. That is information you can act on.

### From Calculation to Decision

The output is not a mandate. It is a sanity check. Three rational responses exist.

**Run the test as calculated.** If the required duration fits your roadmap and the MDE matches your business threshold, launch and do not peek at results until the sample size is reached. Resisting the dashboard is the hard part, but it is the entire point.

**Increase the MDE.** If you cannot afford a 44-day test, ask whether you can afford missing only larger effects. Setting MDE to 25% relative lift (detecting a jump from 3% to 3.75%) reduces the required sample size dramatically. With 500 daily visitors, you might finish in a week. The tradeoff is explicit: you accept that a 10% lift will go undetected. This is not failure; it is clarity. You are choosing to hunt salmon with a net sized for salmon.

**Skip the test.** If your traffic is 100 visitors per day and your baseline is 1%, detecting any realistic lift could require months. The honest move is to acknowledge that an A/B test on that page is not the right measurement tool. Alternatives include qualitative research, session replays, or rolling out the change and monitoring the trend line over time, accepting that you cannot attribute causation precisely.

None of these responses involves pretending your two-week test with 300 visitors per variant produced a reliable "no winner." That pretense is the source of most wasted experiment cycles.

### Why Platforms Keep This Hidden

The major testing platforms are not malicious. Their default sample-size warnings are simply too lenient because they optimize for "get started quickly" rather than "get trustworthy answers." Many tools suggest that a few hundred visitors per variant is sufficient without ever asking for your baseline conversion rate or your MDE. This is analogous to a telescope manufacturer shipping every instrument with the same focus setting and not mentioning that you can adjust it for distance.

By front-loading the calculation, you reclaim ownership of the experiment's design. The five minutes spent entering three numbers into a web calculator prevents the two weeks spent running a test that could never have answered your question. That is not a statistical chore. That is the difference between measuring and gambling.

When someone asks why your team insists on a pre-test duration estimate, the answer is simple: "We would rather know before we start whether our test can see what we are looking for." That sentence alone separates teams that learn from experimentation from teams that merely perform it.

---


---

## References

*Ranked by influence on this article (0–100; higher = more influence). Dated where known.*

1. **100** · 2024 · [Understanding Minimum Detectable Effect in AB Testing](https://www.convert.com/blog/a-b-testing/minimum-detectable-effect-mde-ab-testing/)
2. **83** · 2026 · [Statistical Power in A/B Testing: Avoiding False Negatives](https://atticusli.com/blog/posts/statistical-power-ab-testing-false-negatives/)
3. **83** · 2021 · [Interpreting A/B test results: false negatives and power](https://netflixtechblog.com/interpreting-a-b-test-results-false-negatives-and-power-6943995cf3a8)
4. **62** · n.d. · [The winner’s curse: the BIG problem with enormous lifts in A/B testing](https://guessthetest.com/the-winners-curse-the-big-problem-with-enormous-winners-in-a-b-testing/)
5. **53** · 2025 · [Power Analysis in Marketing: A Hands-On Introduction | Towards Data Science](https://towardsdatascience.com/power-analysis-in-marketing/)
6. **53** · 2026 · [Minimum Detectable Effect (MDE): How to Set It for E-Commerce A/B Tests | DRIP](https://dripagency.de/blog/minimum-detectable-effect)
7. **47** · 2018 · [Master A/B Testing Conversion with This Visual Guide - Call Box](https://www.callboxinc.com/growth-hacking/math-behind-ab-testing-visual-guide/)
8. **47** · 2025 · [Minimum Detectable Effect (MDE) - The Agile Brand Guide®](https://agilebrandguide.com/wiki/statistics/minimum-detectable-effect-mde/)
9. **42** · n.d. · [Understanding Statistical Power and Significance Testing](https://rpsychologist.com/d3/nhst/)
10. **35** · n.d. · [How to determine your A/B testing sample size & time frame](https://blog.hubspot.com/marketing/email-a-b-test-sample-size-testing-time)
11. **23** · 2026 · [Etsy Engineering | Mitigating the winner’s curse in online experiments](https://www.etsy.com/codeascraft/mitigating-the-winners-curse-in-online-experiments)
12. **21** · 2025 · [The Winner's Curse in A/B Testing: Why Your Test Wins Always Get Smaller In Production | Atticus Li](https://atticusli.com/replication-crisis/ab-testing-winners-curse/)
13. **20** · 2024 · [Understanding statistical power in A/B testing | by Thao Trang Nguyen | Medium](https://medium.com/@thaotrangk49clc3/understanding-statistical-power-in-a-b-testing-4a7af48e3d64)
14. **18** · n.d. · [The ultimate guide to correctly calculating A/B testing sample](https://guessthetest.com/calculating-sample-size-in-a-b-testing-everything-you-need-to-know/)
15. **15** · 2021 · [5 ways to Increase Statistical Power - Towards Data Science](https://towardsdatascience.com/5-ways-to-increase-statistical-power-377c00dd0214/)
16. **11** · 2024 · [Minimum Detectable Effect (MDE) • SplitMetrics](https://splitmetrics.com/resources/minimum-detectable-effect-mde/)
17. **11** · n.d. · [What is A/B Testing? An Advanced Guide + 29 Guidelines - Alex](https://alexbirkett.com/ab-testing/)
18. **11** · n.d. · [A/B Testing Framework Implementation: A Beginner’s Guide to](https://techbuzzonline.com/ab-testingframework-implementation-guide/)
19. **11** · n.d. · [Why Most A/B Tests Are Lying to You | Towards Data Science](https://towardsdatascience.com/why-most-a-b-tests-are-lying-to-you/)
20. **8** · n.d. · [How to avoid common data accuracy pitfalls in A/B testing | Kameleoon](https://www.kameleoon.com/blog/data-accuracy-pitfalls-ab-testing)
