# Ops-to-pricing bridge

Verdict: keep restrictions and human escalation; do not enable `ops_aware_stay` until
paired simulation measures demand loss. The current stay objective assumes each candidate
sells, so it can prefer a longer stay while overstating realized revenue.

Alternatives to measure in the proving ground are gap-night restriction, no-check-in on
crew-short days, and closed-to-arrival suggestions. The safest first policy is a human
review flag or a suggested minimum stay that is never pushed. Any automatic restriction
must report false restrictions and its simulated revenue cost against the flat baseline.

