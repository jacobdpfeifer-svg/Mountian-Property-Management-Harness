# Memory contract: evidence may inform; it may not take control

This is the proposed interface between a private operator file and the pricing engine.
It is intentionally narrower than “memory.” A file is evidence. A reviewed, typed,
time-scoped claim is the only thing that may become a deterministic feature. The engine
still chooses price under the existing doctrine and guardrails.

## Absolute prohibitions

- No raw file text, embedding, OCR transcript, LLM output, file name or chat message
  enters `src/compose` or changes a price directly.
- No extractor, reviewer UI, folder watcher or browser receives Guesty credentials or
  a `set_rate` route. The browser never reaches Guesty.
- A claim may not lower a hard floor, raise a hard ceiling, relax move caps, bypass a
  blackout, promote autonomy, alter comp freshness/coverage, or edit YAML/policy.
- No file bytes, transcript, guest PII, owner real name, secret, or credential is put
  in git, the existing iCloud Desktop workspace, recommendations, reason text or test
  fixture.
- No price-bearing owner/portfolio scope in v1. It must name exactly one canonical
  property ID (`summit_haus`, `overlook_ridge`, or `cloud_9`).

## Storage and intake boundary

The implementation creates a private application directory outside the repo and iCloud,
for example `~/Library/Application Support/MontLuxePricing/` (the deployment checklist
must verify it is excluded from cloud sync, mode `0700`, and protected by the logged-in
macOS account/FileVault). It contains:

```text
operator_memory.db              # metadata, claims, audit only; SQLite with FKs on
files/<uuid>                    # immutable original bytes, generated name, never source name
quarantine/<uuid>               # rejected/suspicious byte stream pending delete/export
inbox/                           # local Finder drop target; not a source of truth
receipts/YYYY-MM-DD/<run>.html  # render only; no raw document content
```

`operator_memory.db` is a **sidecar**, not a second pricing DB and not one database per
owner. It is a single-device, single-operator-tenant private store. The main price DB
holds only stable references/hashes required for reproducibility. A future backup must
use a SQLite-consistent backup plus encrypted local destination; copying a live WAL file
by hand is not a backup protocol.

## Accepted and rejected initial file types

| Initial disposition | Types | Reason |
|---|---|---|
| Accept into quarantine for review | PDF (`application/pdf`), UTF-8 `.txt`/`.md`, JPEG/PNG/HEIC image, M4A/WAV audio | Covers rate sheets, notes/photos and voice memo evidence with bounded parsers. |
| Accept only through existing structured workflows | Guesty/API sync, CSV/iCal for inventory/comps | They are observations, not private memory; preserve idempotent ingest and `COMP_DATA.md` gates. |
| Reject in v1 | ZIP/RAR/7z, Office macros, executable/script, HTML, EML/MSG, database files, password-protected/encrypted archive, unknown/mismatched MIME | Avoid macro/archive/parser and email identity risks. Forwarded email may be added later only with a dedicated privacy review. |

Every intake verifies filename normalization, byte limit (25 MiB), allowlisted extension,
magic bytes/content type, SHA-256, malware scan and parser time/page/duration limits.
No archive is expanded. A mismatch, scanner failure, PII/secrets hit, malformed document,
or queue overflow remains `quarantined`, produces no claim and asks the operator to
delete or export it. Success means “eligible for review,” never “remembered.”

## State machine

```text
inbox → quarantined → scanned → stored → extracted → proposed
                                               │          │
                                               │          ├─ confirm → active
                                               │          ├─ reject  → rejected
                                               │          └─ conflict → conflicted
                                               │
                                               └─ delete/export → deleted (metadata tombstone)

active → expired | superseded | revoked
```

The human confirmation captures actor, timestamp, exact claim revision and stated
effect. A language model, if enabled, runs only in a sandboxed, no-tool extraction step
and can emit a typed *proposal*. Deterministic validators own activation. OCR and audio
transcription are treated the same way: untrusted evidence, not instruction.

## Minimal schema

Names are proposals for a new sidecar migration, not tables to add in this research
session.

```sql
memory_files(
  file_id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, storage_key TEXT NOT NULL,
  original_name_redacted TEXT, detected_mime TEXT NOT NULL, byte_count INTEGER NOT NULL,
  intake_source TEXT NOT NULL, status TEXT NOT NULL, pii_status TEXT NOT NULL,
  received_at TEXT NOT NULL, retained_until TEXT, deleted_at TEXT
);

memory_extractions(
  extraction_id TEXT PRIMARY KEY, file_id TEXT NOT NULL REFERENCES memory_files,
  extractor_version TEXT NOT NULL, transcript_hash TEXT, extraction_status TEXT NOT NULL,
  injection_flags_json TEXT NOT NULL, created_at TEXT NOT NULL
);

memory_claims(
  claim_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, file_id TEXT REFERENCES memory_files,
  parent_claim_id TEXT, kind TEXT NOT NULL, property_id TEXT,
  scope_type TEXT NOT NULL, stay_from TEXT, stay_to TEXT, value_json TEXT NOT NULL,
  effect_class TEXT NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL,
  accepted_by TEXT, accepted_at TEXT, review_after TEXT, supersedes_claim_id TEXT,
  source_excerpt_hash TEXT, created_at TEXT NOT NULL,
  UNIQUE(claim_id, revision)
);

memory_events(
  event_id TEXT PRIMARY KEY, claim_id TEXT, file_id TEXT, event_type TEXT NOT NULL,
  actor TEXT NOT NULL, payload_hash TEXT NOT NULL, occurred_at TEXT NOT NULL
);
```

Foreign keys are enabled; state changes append `memory_events` and create a claim
revision rather than overwriting source meaning. `value_json` is validated against a
small per-kind schema. Raw transcript is optional, separately protected and never copied
to the price DB. `source_excerpt_hash` lets the receipt prove a claim came from a
specific evidence span without displaying sensitive text.

## Claim vocabulary and allowed effect

| Kind | Scope | Can affect price? | Deterministic effect |
|---|---|---:|---|
| `annotation` | property/owner/portfolio | No | Receipt context only. |
| `question` | property/owner/portfolio | No | Opens an explicit operator question; no compose input. |
| `property_fact` | exact property | No in v1 | Flags an inventory/config review (for example, sleeps discrepancy); requires the existing source-of-record correction. |
| `comp_trust_note` | property/market | No | Links a comp-review task; cannot add a comp or change coverage/freshness. |
| `operator_rejection` | exact recommendation/property/date | No initially | Outcome/eval evidence; later may propose a reviewed experiment, never a direct adjustment. |
| `minimum_rate` | exact property + finite date range | Yes, after confirmation | `effective_floor = max(policy_floor, claim.minimum)`; reject/escalate if above ceiling or malformed. |
| `no_decrease` | exact property + finite date range | Yes, after confirmation | `effective_floor = max(policy_floor, listed_price_at_run)`; only protects against a downward move, still respects ceiling/move cap/blackout. |

Price-bearing claims are additionally limited to 90 days per revision, require a
`review_after`, start `proposed`, and are **advisory-only** for their first accepted
cycle: the receipt shows their counterfactual effect but `handle` cannot auto-push on
their account. Reconfirmation after review is a policy decision, not a quiet extension.
A claim that would make floor exceed ceiling produces `escalate`; it is never resolved
by choosing either side.

## Scope, freshness, contradiction and compounding

- `property_id` is canonical and mandatory for price-bearing claims. Display labels and
  owner IDs are never matching keys. A “both twins” instruction creates two explicit
  claims with two confirmations.
- An active claim is usable only if `accepted_at <= as_of`, its effective range covers
  the stay date, it is not expired/revoked/superseded, and it passes current validation.
  This prevents future knowledge entering historical evaluations.
- Exact SHA-256 means file N+1 can be a no-op duplicate. Semantic similarity can propose
  a duplicate/contradiction link, but cannot merge or supersede. Same kind, property and
  overlapping dates with incompatible values becomes `conflicted` and is excluded.
- Each accepted/rejected claim becomes feedback: “same Christmas rule seen again,”
  “owner changed their mind,” or “the operator rejected a $X decrease.” This is the
  compounding loop. It reduces repeated review and produces a narrower set of validated
  constraints; it does not lengthen prompts.

## Engine contract and reproducibility

`build_memory_features(property_id, stay_date, as_of)` is the only pricing-facing API.
It returns a deterministic, validated structure such as:

```json
{
  "schema_version": "memory_features_v1",
  "memory_set_hash": "sha256:…",
  "active_claim_refs": ["claim:abc@2"],
  "effective_floor_raise": 125.0,
  "counterfactual_floor_raise": 0.0
}
```

The builder never receives raw content. Compose adds the feature-set hash, feature
builder version and ordered active claim references to its current `inputs_hash` payload
and records a `memory_constraint` reason only when its signed dollar contribution is
non-zero. `rule_version` remains the policy version; `memory_feature_version` is an
additional persisted field, not a disguised policy edit. Existing recommendations with
no memory have an explicit empty set hash (`memory_features_v1:empty`) so behavior is
replayable and additive.

The receipt can show two deterministic counterfactuals for an active claim: with and
without its resulting feature under the same `as_of`, policy and data. It may never say
“the PDF chose $X.” Evaluations pin the `as_of`, policy/model versions and memory-set
hash; a later upload cannot alter a historical result.

## Measurement loop

For every accepted claim, retain: counterfactual recommended price, actual final price,
operator acceptance/override, booking outcome when available, and review/expiry result.
The weekly “memory exam” asks up to three facts that should be represented by active
claims (for example, “Which property has a no-decrease instruction for Christmas?”).
A failed answer, stale claim, no measurable effect, or repeated override is a prompt to
revoke/narrow the claim—not evidence to add more embeddings.
