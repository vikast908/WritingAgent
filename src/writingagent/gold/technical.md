# Gold exemplar — technical register (match precision and example-first habit)

A retry is not a fix; it is a louder version of the same request. If the first call failed
because the database was saturated, the second call arrives while it is still saturated,
plus now there are two. This is why naive retries turn a brief slowdown into an outage: the
client fleet synchronizes on the failure and hammers the recovering service in lockstep.

The remedy is to make every retry cost something and arrive at a different time. Exponential
backoff with full jitter does both. Wait a base delay, double it on each attempt up to a cap,
then sample the actual sleep uniformly between zero and that bound:

```python
delay = random.uniform(0, min(cap, base * 2 ** attempt))
```

The cap bounds the worst case; the jitter spreads the herd. In practice, moving from fixed
to jittered backoff on a 500-node fleet cut recovery time after a dependency blip from
roughly 90 seconds to under 10, with no change to the service itself.
