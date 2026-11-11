# External blockers and requests

Date: 2026-10-20. Nothing here was sent. Copy the request text and send it from the operator's own account when they choose to.

Filled mappings and exports go in gitignored `imports/private/`. Tracked templates stay in `config/data_mapping/`. Do not include guest names, payment data, listing ids, street addresses, or raw statement files in git.

## 1. Channel settlement and owner statements

- Owner: accounting.
- Artifact: reservation-level settlement lines and one monthly owner statement per home, net of the statement, with a stable reservation key and a statement id.
- Land in: `financial_ledger` via [accounting_ledger.template.yaml](../../../config/data_mapping/accounting_ledger.template.yaml) and `owner_statement` via [owner_statement.template.yaml](../../../config/data_mapping/owner_statement.template.yaml).
- Acceptance: `reconcile_statement` is `reconciled` for at least 99% of statements by count and by value, and `wp-price owner-net-month` can return `settled` for a month that is actually fully settled. Pending Guesty booking money does not pass.
- Unblocks: realized owner-net measurement.

Request:

> Please send a de-identified export of channel settlement and payout lines, and the monthly owner statements, for Summit Haus, Overlook Ridge, and Cloud 9. Each money line needs a stable reservation id or a statement id, the property, the channel, the category (lodging, retained guest fee, channel fee, payment fee, management fee, cleaning cost, consumables, maintenance, refund, concession, chargeback), the amount, currency, settled or pending, and the settled time. Each statement needs the owner, the property, the period, and the reported owner net. No guest names, no bank details, no card data.

## 2. Fee treatment and listing confirmation

- Owner: operator.
- Artifact: written confirmation of the Guesty listing map already stored in gitignored `config/local/listings.yaml`, plus management-fee treatment by home and channel, channel and payment fee treatment, which guest fees are retained versus pass-through, and how cleaning, turns, and maintenance are charged. Also name each home's actual jurisdiction (Town of Fraser, Town of Winter Park, or unincorporated Grand County) from a map or permit, not from a mailing city.
- Land in: operator note kept out of git, and `management_fee_pct` only after that note exists. Do not invent the percent.
- Acceptance: owner-net field classes for those terms can move from `missing` to `actual` because a source line or a written term exists. Jurisdiction fields in `config/portfolio/mont_luxe.yaml` are no longer null without a source.
- Unblocks: complete owner-net labels. It does not by itself create settled profit.

## 3. Reservation and calendar history beyond the live read

- Owner: Guesty admin, only if the read API is not enough.
- What the read API already provided on 2026-10-20: 78 in-scope reservations accepted, 45 calendar days (forward window only), 0 settled lines. Two reservations quarantined because nights did not match the dates.
- Artifact still needed: a historical calendar (rate, minimum stay, block status, observed time), not only the forward window.
- Template: [calendar_observation.template.yaml](../../../config/data_mapping/calendar_observation.template.yaml) and [reservation.template.yaml](../../../config/data_mapping/reservation.template.yaml).
- Acceptance: ingest with no `UNKNOWN_IDENTITY`, and every quarantine reason listed.
- Unblocks: a price-decision to reservation trace that includes the rate that was listed when the guest booked. It still does not settle money.

## 4. Operations costs

- Owner: operations lead.
- Artifact: turns, cleaning, consumables, maintenance, refunds, and incidents, with property, date, cost, and reservation key when the cost belongs to a stay.
- Template: [ops_tasks.template.yaml](../../../config/data_mapping/ops_tasks.template.yaml).
- Acceptance: import health fresh, and costs land on a reservation or a statement period. Unlinked money quarantines.
- Unblocks: actual cleaning, consumables, and maintenance in owner net.

## 5. Capacity-matched comps

- Owner: whoever buys or operates the comp source.
- Artifact: observations with timestamp, bedrooms or sleeps, and an explicit price basis (nightly or stay total, fees in or out). Availability method stated.
- Template: [market_observation.template.yaml](../../../config/data_mapping/market_observation.template.yaml). An unlabeled total is left unmapped on purpose and will quarantine as `AMBIGUOUS_PRICE_BASIS`.
- Acceptance: zero usable rows with an unknown basis.
- Unblocks: comp evidence for a future model. It does not repair `EXP-PACE-V3-001`, which is REWORK.

## 6. System cost for the hurdle

- Owner: operator.
- Artifact: copy [config/local/system_cost.example.yaml](../../../config/local/system_cost.example.yaml) to gitignored `config/local/system_cost.yaml` and fill annual system operating cost (data, vendor, hosting, support, allocated implementation) and annual sellable nights. Per home, also fill cost shares, that home's nights, and the allocation method.
- Acceptance: `owner_net_hurdle` status `supplied`, and the per-property rates use each home's own nights.
- Unblocks: the payback hurdle. It is not profit.

## 7. Shadow runtime

- Owner: operator.
- Artifact: verified release, launchd or equivalent calling `wp-price shadow-day` daily, receipts kept, no Guesty write credential on that job.
- Acceptance: 30 calendar days in `shadow_report` with `rate_writes` 0.
- Unblocks: the shadow gate. It does not prove revenue lift.

## 8. Canary authority (do not start)

- Owner: owner plus operator.
- Artifact: separate write credential, signed scope, `DEPLOYED_SHA`, managed database and secret store, external alerts, encrypted off-host backup, frozen field plan, evaluation PASS, 30 shadow days.
- Acceptance: `wp-price canary-packet` prints `READY_FOR_HUMAN_AUTHORIZATION` because those files exist. The tool must not be the author of the signature.
- Unblocks: a human decision to run a canary. It does not run one.

## Also unchanged

Webhook signing secret, public-repo CI approval, and a history purge of old listing ids remain as in [docs/reports/final_delivery/EXTERNAL_REQUESTS.md](../final_delivery/EXTERNAL_REQUESTS.md). They are not the profitability measurement.
