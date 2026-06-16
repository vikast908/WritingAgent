# Gold exemplar — business register (match BLUF, quantified, decision-oriented)

Recommendation: migrate the billing service to the new provider this quarter. The switch
costs roughly $40,000 in engineering time and one weekend of scheduled downtime, and it
removes a single point of failure that took us offline for four hours in January.

We considered three options. Staying put is free today but leaves us exposed to the same
outage, which we estimate at $180,000 in revenue per occurrence. A full rebuild gives us the
most control but takes two quarters and pulls the team off the roadmap. The migration
captures most of the resilience benefit at a fraction of the rebuild's cost and time.

Decision needed by February 14 to hold the maintenance window. If we slip past that date,
the next low-traffic weekend is in April, and we carry the outage risk until then.
