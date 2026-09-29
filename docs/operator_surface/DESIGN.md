# The Mont Luxe Run Receipt + Evidence Inbox

## One-page operator pitch

**Sunday:** after the normal recommendation run, open one local dated **Run Receipt**.
It says either “No decision needs you” or presents the few changes worth attention:
what moved, why the engine is allowed to say that, how weak the evidence is, and whether
anything was pushed or deliberately not pushed. For a night, it shows the route
`floor → listed → recommended → ceiling`, the existing plain-English reasons, and exact
audit facts on demand. The Northwoods twins share a spine so a split cannot hide. Rate
action remains in Guesty.

**Monday:** drag a rate sheet, owner-note photo, or voice memo into **Evidence Inbox**
in Finder. The program stores it privately, checks it, and proposes a small attributable
claim, such as “312: do not decrease these Christmas nights.” You review that exact
claim on the next receipt. It does nothing until you confirm it.

**Friday:** a subsequent recommendation can demonstrably differ because an accepted,
property-scoped constraint was deterministically present. The receipt shows the claim
ID and a “without this claim” counterfactual. Rejections and contradictions become
evidence too; a pile of PDFs does not.

**Never:** an LLM chooses a price; a file bypasses guardrails or comp-quality gates; a
floor/ceiling silently changes; Guesty credentials enter a browser; or this becomes
another calendar, SaaS tenant, or chatbox.

## Recommendation

Build **receipt first, then evidence inbox**, locally. This reshapes the initial sketch:
Finder—not a web upload widget—is the first drop surface; a generated local HTML
receipt—not a dashboard—is the price surface.

This is still a frontend: an HTML receipt that opens and prints without a server. A later
loopback-only review page may make claim confirmation easier, but neither surface becomes
a rate writer or Guesty client.

Why it wins:

- Current truth requires skepticism: the 2026-09-25 audit found empty Northwoods
  exports, Cloud 9 cold-start recommendations, uncalibrated pacing and zero writes.
  Attention routing is more valuable than a calendar.
- `format_owner_recommendation` and persisted reason data already establish a faithful
  vocabulary. Reuse them; do not invent “agent thoughts.”
- A local receipt reduces privacy, availability and maintenance burden while Guesty
  remains visibly authoritative.

Concrete, testable testrun counterfactual: if an owner had confirmed a `cloud_9`
`no_decrease` claim for the peak dates where the frozen run recommended $1,265 while
the later Guesty calendar was far higher, the builder would have raised only those
candidate lower bounds to the listed rate. The receipt would show the claim and its
counterfactual; if that lower bound exceeded the engine ceiling it would escalate rather
than push. This is an example to test, not evidence that such an owner instruction exists.

## Primary view

File name: `receipts/YYYY-MM-DD/<run_id>.html`. The first screen is short; print or
expand for audit detail. It renders even with no memory or a degraded run.

```text
MONT LUXE — RUN RECEIPT                         Sun Sep 29, 7:08 AM
Scope: 312 Northwoods · 300 Northwoods · Cloud 9     Guesty is the rate record

TODAY'S POSITION
  Suggestions only — comp coverage is thin; nothing was pushed.  [Why?]
  Since last receipt: 9 suggested · 0 pushed · 2 held · 1 memory claim pending

LOOK AT THESE FIRST
  NORTHWOODS TWINS · Dec 24–26
  312 Dec 25   $2,600 listed  →  $2,845 recommend  →  $3,000 ceiling
  floor $1,800 ───────── listed $2,600 ─────● rec $2,845 ───── ceiling $3,000
  Christmas demand supports a higher rate.
  The top of the range leans on seasonal history; comparable evidence is thin.
  [Why this?] [Exact receipt] [Open date in Guesty]

  TWIN CHECK ─ 312 +$245 / 300 unchanged
  Different listed rate or evidence, not a hidden shared policy. [Compare]

ALSO WATCH
  Cloud 9 · Jan 8–10 · held near listed price — weak ceiling; suggestion only
  Jan 15 · no change recommended

TRUST TIMELINE
  06:59 comps degraded (coverage 42%) → autonomy suggest; no push attempted
  07:08 receipt created; 0 channel writes

EVIDENCE INBOX
  Finder › Mont Luxe Evidence Inbox
  Pending: owner-note.pdf → 312 / Dec 24–26 / no decrease
  [Review proposal] [Reject] [Why it cannot set a price]
```

### Receipt rules

1. **Rank attention, not time.** Cluster only consecutive nights with the same
   reason/guardrail/memory set. A twin split, weak ceiling, blocked/escalated night,
   unpushed handle run, or ≥$100 move is its own card.
2. **Use stored truth only.** Main sentences are existing owner renderings or their
   exact templates. Expanded detail can show reason code, contribution, range, hash,
   versions and request ID.
3. **Show absence.** No comp evidence, weak ceiling, held near listed, health demotion,
   and no channel write are first-class states—not green silence.
4. **No policy editor.** No sliders, global overrides, base-rate controls, or bulk
   calendar edits. Guesty links are informational only.
5. **Claims, not rates.** The thin slice acts in Guesty for rates; a later UI confirms
   only a typed memory claim.

## Information architecture

| Surface | Job | Reads | Writes | Never does |
|---|---|---|---|---|
| Run Receipt | Explain a run under a minute. | Main DB recommendations, health/rate facts, safe claim summaries. | HTML/PDF render only. | Set rate, edit policy, parse documents. |
| Exact detail | Audit one decision. | Persisted components, reasons, hashes, versions, claim refs. | None. | Generate a new story or show raw PII. |
| Finder Inbox | Give one file. | None. | Move bytes into quarantine. | Treat drop as approval. |
| Claim review (phase 2) | Confirm/reject/narrow/supersede. | Redacted claim/file metadata. | Append claim/event revision. | Change Guesty/policy/guardrails. |
| Guesty | Review or act on rates. | Guesty calendar. | Existing Guesty rate action. | Receive browser calls. |

The requested drop zone exists in the operating system where the team already receives
files. The receipt makes the outcome discoverable and creates a human confirmation step.

## Backend boundaries

```text
main pricing SQLite
Guesty → sync → features → compose + guardrails → recommendations → receipt renderer
                         ▲              │                 │
                         │              │                 └ existing guarded push only
                         │              ▼                   (never browser/extractor)
                         │      deterministic memory features
                         │              ▲
private file → quarantine → extract → proposed claim → human confirm
                                 │
                           sidecar operator_memory.db
```

The feature builder is called by the normal recommendation path before price search and
returns only validated typed values. It cannot write policy. Compose adds the feature-set
hash to `inputs_hash`, stores claim refs/version, and emits a reason only if the feature
contributed dollars. `MEMORY_CONTRACT.md` defines schema, limits and as-of behavior.

Important implementation choices:

- No browser database access. Receipt uses a local process; phase-2 loopback handlers
  authenticate the OS session and accept narrow claim commands with CSRF protection.
  Localhost alone is not authorization.
- No raw document in main SQLite. Use app-support storage, a separate SQLite sidecar,
  generated IDs, and protected retrieval.
- No LLM requirement. If later used, an LLM is a sandboxed, no-tool claim proposer;
  deterministic validators and human confirmation still control activation.
- A claim label is not a reason. It renders only when its typed feature changed a
  deterministic bound/candidate and has an actual signed contribution.

## Thin-slice build order (only after approval)

1. **Receipt read path:** add `wp-price receipt --run-id …`, HTML/print CSS, and tests
   mapping every visible sentence to stored facts. Include health timeline, no-push
   outcomes and a twin comparator. No migration beyond optional receipt metadata.
2. **Sidecar foundation:** private application-support path checks, SQLite migration,
   quarantine/store, hash/type/size/malware hooks, deletion/export procedure and
   `wp-price memory status`. Never put private data under this repo.
3. **Claim intake:** `annotation`, `question`, `minimum_rate`, `no_decrease`; deterministic
   validation, CLI confirmation and receipt card. Start only with contract-listed types.
4. **Feature + replay:** as-of builder, recommendation provenance fields,
   `memory_constraint` reason, counterfactual and no-memory equivalence tests. First
   accepted claim cycle remains suggestion-only.
5. **Claim-review page:** only if CLI confirmation proves awkward. It is a loopback
   convenience, not a framework or pricing console.
6. **Evaluate before expansion:** weekly memory exam; compare counterfactual, final
   price, outcome and overrides; then decide if email/audio/notification merit risk.

## Acceptance criteria

- A fixed `run_id` renders stable receipt content and exposes every stored weak-ceiling,
  guardrail and health-demotion fact.
- No receipt can show a reason absent from that recommendation’s persisted JSON.
- No-memory recommendation output is equivalent except for empty-memory provenance.
- Rejected/conflicted/expired/wrong-property/future-accepted claims have zero effect,
  including historical `as_of` backtests.
- An accepted valid `no_decrease` affects only the named property/dates and cannot violate
  hard guardrails; floor-above-ceiling escalates.
- Fake injection PDF, ZIP bomb, renamed executable and PII file create no active claim
  and leak no raw content to logs/receipts.
- Browser/extractor code cannot import Guesty credentials or rate-writing code.
- At thirty doors, add filters and assignment/digests—not another tenant, browser write
  path, or non-property-scoped memory.

## Decision requested

Approve this **receipt-first, evidence-inbox second** thin slice before application code,
migrations, watcher, framework or local server is written. Two build-time choices remain:
private-storage/backup policy and who may confirm a price-bearing memory claim. Neither
needs a browser-to-Guesty path.
