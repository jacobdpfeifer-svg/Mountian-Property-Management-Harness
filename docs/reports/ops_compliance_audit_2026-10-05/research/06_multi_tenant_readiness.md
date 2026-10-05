# Multi-tenant readiness

Verdict: not ready for a 50-home manager without stronger tenancy boundaries. Profiles,
rule packs, and owners are keyed by property/owner, which is a good start. The remaining
risks are shared process configuration, source aliases, crew zones, reviewer identity,
and private output paths.

Required next design work: tenant_id on every operational row and output, per-tenant
portfolio and rule-pack roots, role-based evidence access, per-tenant source credentials,
and an isolation test that proves one owner/tenant cannot appear in another receipt or
incident action.

