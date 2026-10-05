# Turn model

Verdict: keep turn + slack + shrinkage, then add a thin scheduling layer when the
portfolio exceeds one shared crew per zone. The current abstraction is interpretable,
auditable, and matches the operator’s mental model. A full queueing model would be more
realistic for shared crews but would be harder to calibrate and explain.

The immediate change is DST-aware elapsed windows (implemented in this audit), followed
by empirical travel distributions, crew overlap, and freshness-aware confidence. A rule
checklist remains useful as evidence collection but should not replace the numeric slack
model.

See [Breezeway’s developer portal](https://developer.breezeway.io/) and [Turno’s public
API documentation](https://apidocs.turnoverbnb.com/) for the kinds of task fields an
adapter would need to preserve.

