# Operator surface audit — 2026-09-29

Scope: the five design documents **and** the shipped receipt/memory implementation in
`src/receipt`, `src/memory`, compose, schema, CLI and their targeted tests. This is an
implementation audit, not a new product proposal.

## Verdict

**Pass with enforced scope.** The thin slice now holds the pricing boundary: a file
cannot directly price, a price-bearing claim is typed/property-scoped/confirmed, compose
records its deterministic provenance, and every memory-touched recommendation is
suggest-only. The receipt is derived from persisted recommendation facts and no browser
has a Guesty route.

The feature must not be described as a general PDF/photo/audio memory system yet. Those
formats are intentionally quarantine-only because v1 does not have a PII or claim
extractor for them. Markdown/text is the sole automatic proposal format, and it requires
a clean installed ClamAV scan. That narrowed promise is safer and more honest.

## Evidence checked

- Contract alignment: pricing doctrine, autonomy, comp-data rules, compose and owner
  presentation paths, main/sidecar schemas, CLI routes, and current testrun truth.
- Authority graph: no `src.memory`/`src.receipt` import can reach `src.pms` or Guesty;
  the existing push remains the only write path.
- Provenance: `memory_set_hash`, feature version, claim refs and counterfactual price
  are persisted with a recommendation and included in `inputs_hash`.
- Safety behavior: hostile content, PII text, ZIP/executable disguise, stale/future and
  cross-property claims, conflict, ceiling clash, empty memory and receipt fidelity.
- Packaging: `src.memory/schema.sql` is now declared as package data instead of working
  only from a source checkout.

## Findings and dispositions

| Severity | Finding | Disposition |
|---|---|---|
| S1 | The initial contract said a price-bearing claim was advisory only for its “first accepted cycle,” but code had no cycle identity; in practice a non-zero contribution was forever `suggest`-only. | **Fixed/clarified:** every active price-bearing claim now demotes `handle` to `suggest` in v1. This is safer than the ambiguous promise. |
| S1 | The receipt hard-coded all three properties even for a single-property run, making the scope look broader than the underlying recommendations. | **Fixed:** scope is derived from rows in the selected run. |
| S1 | A pending `minimum_rate` card did not show the dollar value, so a human could confirm a price-bearing claim blind. | **Fixed:** the redacted typed minimum is shown; raw evidence remains hidden. |
| S1 | `src.memory/schema.sql` was not listed as package data, so an installed wheel could fail when initializing the sidecar. | **Fixed:** package-data declaration added. |
| S1 | Missing `clamscan` was treated as clean; the documented malware gate was therefore not real. | **Fixed:** scan is fail-closed. Text stays quarantined when scanner is absent, fails or detects malware. |
| S1 | PDF/image/audio intake was marked clear despite no PII or claim extraction. | **Fixed/contained:** these formats are quarantine-only (`manual_privacy_review_required`) until a dedicated privacy/parser review. |
| S2 | A 400-file flood could keep copying rejected files to quarantine, and the inbox read full oversized files into memory. | **Fixed:** queue overflow records metadata only; oversized Finder files are streamed-hashed and moved without a full-memory read; symlinks are rejected. |
| S2 | Invalid/non-finite claim values or malformed sidecar dates could throw in the pricing path. | **Fixed:** finite validation, date parsing guards and invalid-row exclusion added. |
| S2 | Conflicted claims could not be superseded; unrelated claims could be used to supersede one another. | **Fixed:** a conflicted incoming claim may resolve its matching conflict; kind/scope/property/range must match. |
| S2 | Receipt timeline counted only applied writes, hiding failed and dry-run outcomes. | **Fixed:** distinct applied/failed/dry-run counts are rendered. |
| S3 | Sidecar writes lacked the main DB’s busy timeout/WAL posture. | **Fixed:** foreign keys, 10-second busy timeout and WAL attempt are configured. |

## Comprehensive stress-test matrix

| Attack | Expected invariant | Audit result |
|---|---|---|
| Explanation theater | Receipt text comes only from persisted reason messages; audit details use stored hashes/versions. | **Pass.** Renderer escapes content and tests reject an invented `snow_demand` sentence. |
| Memory override | No file/LLM/brower can lower a floor, lift a ceiling, relax guardrails or call Guesty. | **Pass.** Only `minimum_rate`/`no_decrease` produce a lower-bound raise; floor-over-ceiling blocks/escalates; memory run is suggest-only. |
| Stale instruction | Claim expires deterministically and cannot apply before acceptance. | **Pass.** `accepted_at <= as_of`, finite stay range and hard `review_after` expiry are tested. |
| Twin split | Claim must bind to one canonical property; a shared-owner label cannot price both. | **Pass.** Validator rejects “both”; receipt shows twin difference from stored rows. |
| Prompt injection | Instructions in text/PDF/photo cannot gain tool authority. | **Pass with scope.** Text flags instruction-like content and can only propose a typed claim; PDF/photo/audio never parse in v1. |
| Contradiction | Overlapping incompatible minima cannot silently pick a winner. | **Pass.** Both claims become conflicted; only a matching explicit supersession resolves them. |
| Silent push | A handle candidate and write outcome must be visible afterward. | **Pass.** Receipt shows eligibility/no-push and applied/failed/dry-run counts. |
| Empty brain | Zero sidecar leaves pricing numerically unchanged. | **Pass.** Empty hash/counterfactual regression test. |
| Flood/large file | Intake must not parse or copy unlimited bytes. | **Pass for application-controlled storage.** 20-file metadata queue cap, 25 MiB per direct ingest, streamed oversized Finder handling. Finder itself can still consume disk while the OS copies a file—monitor available disk. |
| Eval leak | A later acceptance cannot alter historical replay. | **Pass.** Point-in-time claim selection and hash provenance are tested. |
| Comp laundering | Personal CSV cannot become a pricing comp input. | **Pass.** Structured formats route/quarantine, no claim. |
| Identity/PII | Raw PII does not enter a recommendation, receipt or normal sidecar metadata. | **Pass for text; deliberately unavailable for binary.** Text detectors quarantine likely email/phone/SSN/card/secret patterns. Binary content is not cleared or parsed. |
| Malicious binary | Unknown, archive, executable and symlink inputs remain inactive. | **Pass.** Type checks, archive rejection, scanner gate and symlink rejection tested/implemented. |
| Installed package | Sidecar schema is available outside source checkout. | **Pass by packaging declaration; wheel installation should remain a release gate.** |

## Residual risks and hard release gates

1. **ClamAV is an operational dependency, not bundled.** A host without `clamscan` now
   fails safely, but cannot ingest text. Provision/update ClamAV and add a deployment
   health check before relying on the inbox.
2. **Binary evidence is not usable yet.** Do not claim that a photo, PDF or voice memo
   makes the engine smarter. Add a dedicated bounded extractor, binary PII controls and
   adversarial fixtures before changing its disposition.
3. **The sidecar is a local privacy boundary, not cryptographic encryption.** FileVault,
   macOS account access, encrypted backup and excluded sync destinations remain operator
   prerequisites. Test that deployment path, not just a temporary test root.
4. **No authorization model beyond the local macOS user exists.** This is appropriate for
   the CLI/Finder thin slice. Any loopback UI must add CSRF/session controls and an
   explicit confirmer policy before it can mutate claims.
5. **Receipt is an audit window, not a live calendar.** It intentionally needs a fresh
   run/receipt to show a rate change. Guesty remains the live source of record.
6. **Repair the build environment, then run a wheel-install smoke test before release.**
   This workspace’s `.venv` lacks both `setuptools` and `wheel`, so `pip wheel` cannot
   import the declared `setuptools.build_meta` backend. The source/test environment is
   healthy; packaging is presently unverified and must remain a release gate.

## Test evidence

Targeted after fixes:

```text
.venv/bin/python -m pytest tests/test_memory.py tests/test_receipt.py -q
18 passed
```

Full fast suite after fixes:

```text
.venv/bin/python -m pytest -q
322 passed, 1 deselected in 26.69s
```

The system Python run is not a valid result in this workspace because it lacks NumPy;
the project virtual environment is the tested runtime. An attempted wheel smoke test
correctly stopped at the missing build backend described above; it did not test a wheel.
