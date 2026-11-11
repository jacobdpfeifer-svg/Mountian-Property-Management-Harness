# Q1 — What buyers use today, and how ours compares

Desk research, 2026-10-06. No vendor demo, trial account, or buyer interview was used.
Vendor capability statements below are **vendor states** (taken from the vendors' own
marketing or docs pages), not tested capabilities. Where a page failed to load the
claim is marked `unverified`.

## Verdict

Our ops layer is **not a task/field-service product** and should not try to become one.
Every operations vendor checked (Breezeway, Operto Teams, Guesty Tasks, Streamline
Property Care) states it does the things a housekeeping manager touches every day:
mobile checklists, required photo uploads, auto-assignment, supply tracking, owner-visible
task photos. Ours does none of those. It has no mobile app, no checklist, no photo, no
UI beyond a CLI, and no notifications. What ours does that none of them state is narrow:
it turns task outcomes into **pricing/min-stay inputs** (turn cost, Beta-shrunk
P(ready on time) by slack bucket, zone capacity) and holds an
**evidence-gated readiness state machine that restricts pricing**, with human-approved
incident actions and a forbidden-action list. That bridge is the differentiator the
research sample argues for. The compliance register competes with nobody directly:
Granicus and Deckard sell to **governments** (they're the enforcement side), and Avalara
MyLodgeTax states it does registration, filing and remittance, which ours doesn't attempt.

- **Task/ops layer (importers, turns, economics): keep, narrowed to "integrate".** Read
  from Breezeway / Guesty Tasks / Turno. Don't build field tooling. The importers are
  untested against real tenants (OPERATIONS.md says so), so today the bridge has no
  verified input.
- **Readiness state machine + pricing gate: keep, differentiate.** No vendor page
  opened describes readiness that gates price or min-stay.
- **Incidents/actions: keep** as a human-approval layer; drafts only.
- **Compliance register: keep as a narrow deadline tracker, and change its positioning.**
  It isn't a Host Compliance/Rentalscape competitor (different buyer). Integrate with
  or defer to MyLodgeTax for tax, and don't build filing.
- **Owner receipt: keep, and change it** to add the readiness/ops "proof block". Guesty's
  owner portal states it already shows cleaning/inspection photos to owners, which our
  HTML receipt can't.

## How operators describe the workflow (research sample, 2026-09-30)

| What the sample reports | Implication for ours |
|---|---|
| Visit Vail names Saturday cleaner cancellation and license expiry as what wears owners down, despite acceptable revenue | Both pains map onto pieces we have (P(ready), compliance deadlines), but neither is wired to a live feed yet |
| Mountain operators differentiate on in-house housekeeping/maintenance, inspections, snow/access readiness (Rendezvous 60+ staff, Tahoe Getaways ground services, SummitCove 100+ employees) | These firms already run field teams in some tool; they will want ours to read that tool, not replace it |
| Public pages rarely disclose PMS/task stack; the sample makes "what was purchased; what is still spreadsheet/text/phone" an interview question | We don't know which task system any target uses, including our own operator (`TODO(operator-confirm)` in OPERATIONS.md) |
| Proposed data contract has `accepted_at, started_at, completed_at, inspected_at, exception_code, verified_by` | `turnover_outcomes` stores `scheduled_start, completed_at, qa_pass, late_ready_minutes`, with no accepted/started/inspected timestamps and no exception code. P(ready) is calibrated on less than the sample asks for |
| Proposed readiness states run `assigned → accepted → in_progress → clean_complete → inspected → systems_verified → guest_ready` | Ours models **property health** (`ready/at_risk/inspection_required/out_of_service/remediation/verified_ready`), not **turn progress**. The two are different machines; the turn-progress one is what task vendors already track |
| Decision boundary: never automatic for access codes, refunds, closures, safety claims, moving money | Matches our `ForbiddenAction` list, which is a real strength |
| Owners want a receipt proving a longer-stay/lower-occupancy decision protected contribution | Owner receipt has revenue decisions, property care and readiness transitions; no per-decision ops proof block yet |
| Decision gate: proceed only if half of 16 interviewees can produce task timestamps | No interviews done. The whole ops bridge is unvalidated demand |

## Operations vendors

| Vendor | Vendor states it does (that ours doesn't) | Ours does (that its opened page doesn't state) | Recommendation |
|---|---|---|---|
| **Breezeway** | Mobile checklists per property; required photo uploads; automated assignment workflows; maintenance schedules and inspections; supply tracking with low-stock thresholds and automatic deductions on task completion; smart-lock/smart-home integrations; guest messaging; reporting to "share the work". API exposes tasks, task requirements, supplies, people, property photos, webhooks | P(ready on time) by slack; turn cost feeding min-stay; readiness that blocks price moves; incident → affected-stays set with approval log | **Integrate.** It is the most likely field tool for 50 to 200-home mountain operators. Our importer paths are "not verified"; verify against a real tenant before claiming support. Consider pulling `task requirements` (checklist completion) and supply data, which we don't read |
| **Turno** | Cleaner marketplace / scheduling / payments (from general knowledge only, **unverified**: turno.com, /features/, /pricing/, help.turno.com all returned 403; API docs page loaded but showed only a title) | Same bridge as above | **Integrate** (importer exists; shape unverified). Turno is more typical of the 3 to 20-home band using contract cleaners (unverified) |
| **Guesty Tasks** | Tasks auto-triggered from reservation events; recurring tasks (annual inspections, routine maintenance); checklists; work orders with expenses; staff photo uploads with timestamps; role permissions; mobile app; owner portal shows cleaning/inspection photos | Turn derivation incl. owner stays; cost and P(ready) estimates; readiness gate on pricing; idempotent intent-before-write for live task creation | **Integrate.** Guesty is our system of record already. Our live task write is gated by `--confirm-live-write`; good. The Tasks API path is "not yet verified on the tenant" |
| **Operto (Teams/Access/Guest)** | Customised checklists; photo **and video** proof; scheduling; payroll and time tracking; inventory with reorder thresholds; "bill owners for replacements with time stamped proof"; laundry/linen management; preventive maintenance; smart locks, noise (Minut, NoiseAware) and thermostats | Pricing/min-stay effects of readiness; Beta-shrunk readiness; compliance register | **Integrate (later).** No Operto importer exists. Its sensor feed is the closest analogue to our generic `telemetry` JSON, which only sets `at_risk` |
| **Hostaway** | Vendor states "task workflows, users and permissions", owner portal and statements. **Task details unverified**: /features/ loaded with only that line; /features/task-management/ and /solutions/operations/ 404; /features/automation/ described messaging only | Everything in the bridge | **Integrate only if a buyer is on Hostaway.** We have no Hostaway connector of any kind; our stack is Guesty-only, which excludes Hostaway shops today |
| **Track (TrackHS → Track Hospitality)** | Vendor states housekeeping and maintenance coordination, native dual-ledger **trust accounting**, owner portal and communications. Inspection/work-order/mobile details not on page (unverified). trackhs.com refused connection; trackhospitality.com loaded | Readiness gate; P(ready) | **Integrate if buyer present; don't match.** Track and Streamline are full PMSs. Trust accounting is explicitly out of scope for us |
| **Streamline** | Property Care app: task assignment, tracking, QC, photo uploads; work orders with trigger-based docs; POS inventory with replenishment triggers; vendor payables; owner statements; trust accounting; smart access codes | Same | **Integrate if buyer present.** Visit Winter Park Lodging (sample #2) uses Streamline, so Grand County buyers may be on it. We have no Streamline connector |

## Compliance vendors

| Vendor | Who buys it | Vendor states it does (that ours doesn't) | Ours does (that it doesn't state) | Recommendation |
|---|---|---|---|---|
| **Granicus Host Compliance** | Local governments | Captures listings from 70+ STR sites; address identification; permit and tax collection forms; flags under-reported tax and occupancy violations; 24/7 complaint hotline; violation letters | Operator-side per-property document register with verifier name and evidence hash; refuses to say "compliant" | **Differentiate (not a competitor).** It is the enforcement side. The useful overlap: it flags listings whose advertised occupancy or permit number doesn't match, which our `listing_match`/`occupancy_check` attempt from the operator side. Ours needs listing text that we often don't have, so the check returns `unverified` |
| **Deckard Rentalscape** | Municipalities (vendor states 500+ jurisdictions) | Monitors 15M+ listings across 10,000+ sites; address matching; permit-registration lift; TOT collection | Same as above | **Differentiate.** Not sold to operators. Our register is a pre-audit for what a Rentalscape-equipped town will see |
| **Avalara MyLodgeTax** | STR owners and property managers | Identifies required agencies; registers properties and **obtains lodging licenses**; renewals; prepares, **files and remits** lodging tax; imports revenue from PMS/Airbnb/Vrbo; updated rates | Fire/life-safety inspection, responsible-agent, fireplace and insurance deadlines; evidence hashing; per-jurisdiction rule packs with review state | **Integrate or refer; don't match.** Tax filing is regulated, money-moving work (forbidden by our doctrine anyway). Our `sales_tax_account` row should accept "filed via MyLodgeTax" evidence. The product page `/products/my-lodge-tax.html` 404'd; the `/mylodgetax/` page loaded |

## Where ours is weaker, plainly

| Gap | Severity for buyer |
|---|---|
| No UI: everything is `wp-price ops …` CLI plus an HTML receipt. Every vendor above ships web and mobile | Disqualifying for a housekeeping manager; acceptable only for an owner/revenue lead in a pilot |
| No verified live connector: Guesty Tasks, Breezeway, Turno importers all "not verified"; CSV presets are "best guesses" | P(ready) and turn cost currently run on profile **estimates** (`basis: estimate`) |
| Single tenant, Guesty-only, three Grand County jurisdictions with rule packs `reviewed_by: null` | Can't onboard a Summit County or Hostaway/Track/Streamline shop without new work |
| Turn data is thinner than the sample's contract (no accepted/started/inspected timestamps, no exception codes) | Readiness calibration is weaker than what buyers' own tools could supply |
| No notifications (grep for `notify|sms|email` in src/ops, src/compliance: none) | An exception queue nobody is pinged about is a report, not a workflow |

## Sources

All opened 2026-10-06 with WebFetch unless marked as a local file.

| URL | Status |
|---|---|
| local: `Harness for my wonderful Mother/docs/reports/MOUNTAIN_OPERATOR_RESEARCH_SAMPLE_2026-09-30.md` | read |
| local: `~/wp-price-worktrees/ops-audit/docs/rules/OPERATIONS.md`, `src/ops/**`, `src/compliance/**`, `src/receipt/owner_monthly.py`, `src/ops/schema.sql` | read |
| https://www.breezeway.io/ | loaded |
| https://www.breezeway.io/inventory | loaded |
| https://developer.breezeway.io/ | loaded |
| https://www.breezeway.io/property-care | failed (404) |
| https://www.breezeway.io/owner-reporting | failed (404) |
| https://www.breezeway.io/features | failed (404) |
| https://turno.com/ | failed (403) |
| https://turno.com/features/ | failed (403) |
| https://turno.com/pricing/ | failed (403) |
| https://help.turno.com/ | failed (403) |
| https://www.turnoverbnb.com/ | redirect to turno.com (403) |
| https://apidocs.turnoverbnb.com/ | loaded (title only, no content) |
| https://www.guesty.com/ | loaded |
| https://www.guesty.com/features/tasks-management/ | loaded |
| https://www.guesty.com/features/homeowners-portal/ | loaded |
| https://www.guesty.com/features/operations/ | failed (404) |
| https://www.guesty.com/features/task-management/ | failed (404) |
| https://www.guesty.com/integrations/turno/ | failed (404) |
| https://open-api.guesty.com/ | failed (404) |
| https://operto.com/ | loaded |
| https://operto.com/teams/ | loaded |
| https://operto.com/connect/ | failed (301, not followed) |
| https://www.hostaway.com/ | loaded |
| https://www.hostaway.com/features/ | loaded |
| https://www.hostaway.com/features/automation/ | loaded (messaging only) |
| https://www.hostaway.com/features/task-management/ | failed (404) |
| https://www.hostaway.com/features/property-management-software/task-management/ | failed (404) |
| https://www.hostaway.com/solutions/operations/ | failed (404) |
| https://www.trackhs.com/ | failed (connection refused) |
| https://trackhs.com/ | redirect to trackhospitality.com |
| https://trackhospitality.com/ | loaded |
| https://trackhospitality.com/track-pms/ | loaded |
| https://www.streamlinevrs.com/ | loaded |
| https://www.streamlinevrs.com/features/ | loaded |
| https://granicus.com/product/host-compliance/ | loaded |
| https://granicus.com/solution/short-term-rentals/ | failed (404) |
| https://www.deckard.com/ | loaded |
| https://www.avalara.com/us/en/products/my-lodge-tax.html | failed (404) |
| https://www.avalara.com/mylodgetax/en/index.html | loaded |
