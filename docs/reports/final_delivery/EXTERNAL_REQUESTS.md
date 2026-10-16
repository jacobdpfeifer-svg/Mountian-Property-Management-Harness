# External inputs needed to continue

Each item names the exact input, who controls it, the repository contract or
test that will accept it, and the gate it unblocks. Request numbers match the
templates in `docs/prompts/FINAL_DELIVERY/07_OPERATOR_OUTREACH_TEMPLATES.md`.
None of these asks for, or implies, a live pricing write except item 9.

| # | Exact input | Controlled by | Lands in | Acceptance test | Unblocks |
|---|---|---|---|---|---|
| 1 | Guesty read-only: calendar history (rate, min stay, status, observed time) and reservation lifecycle export (create/modify/cancel, stay-total lodging and guest fees separated), de-identified, for the three homes | Guesty admin (template 1) | `calendar_observation`, `reservation` contracts | ingest with zero `UNKNOWN_IDENTITY`; quarantine rate reported; `tests/data_spine` patterns | Data PASS path; shadow inputs |
| 2 | Confirmation of each home's Guesty listing id (kept in gitignored `config/local/listings.yaml`) and of `management_fee_pct` per owner | Owner / property manager (template 2) | `PortfolioScope`, owner-net assumptions | `load_scope()` builds without `ScopeError`; owner-net basis becomes `actual_terms` | Scope at live boundaries; owner-net completeness |
| 3 | Channel settlement/payout lines and monthly owner statements (net per statement) | Accounting (template 3) | `financial_ledger`, `owner_statement` | `reconcile_statement` → `reconciled` for ≥99% of money | Realized owner-net measurement |
| 4 | Ops records (turns, inspections, incidents, owner blocks) as export or a read-only Turno/Breezeway/Guesty Tasks credential | Ops lead (template 4) | `ops_task`, `listing_constraint` via `ops.constraint_adapter` | import with health `fresh`; restrictions match provider records | Ops readiness PASS |
| 5 | Capacity-matched comp sample with price basis (nightly vs stay total; fees in/out) and timestamps | Market-data vendor (template 5); may require payment | `market_observation` | zero `AMBIGUOUS_PRICE_BASIS` | Calibration coverage; comp inputs |
| 6 | Real booked shoulder-season nights (≥10) in the aggregate export | Owner / accounting | `data/exports/rate_card.yaml` (gitignored) | `booked_adr_shoulder_spring` becomes measured | V2 calibration coverage |
| 7 | Webhook signing secret (`whsec_…`) and an HTTPS endpoint the operator controls | Guesty admin | `GUESTY_WEBHOOK_SECRET`; wrapper around `handle_delivery` | signed live delivery accepted; tampered one dead-lettered | Live webhook ingress |
| 8 | Decisions on runtime services: managed host/DB, secret store, alert destination, encrypted backup target | Operator | `AlertSink`, `backup_db`, release root | restore drill from the chosen store; alert received | Platform BLOCKED rows |
| 9 | Only after shadow passes: a **separate** Guesty write credential (or a written decision if Guesty cannot issue one) and a signed canary scope — one property, listed dates, floor, max $/% move, max writes, approver, rollback owner, expiry | Owner + operator (Prompt 04) | `GUESTY_WRITE_CLIENT_*`, `write_permit.json`, `CanaryAuthorization` | canary dry-run diff reviewed; all abort tests green | Field-safety gates |
| 10 | Owner approval to (a) push commits to the public GitHub repo so CI runs, (b) rewrite history to purge old listing ids, (c) apply spine migrations to the operator DB | Repository owner / operator | git; `docs/runbooks/DEPLOYMENT.md` §4 | green CI run; scan of rewritten history; `schema_migrations` on live DB | CI, history, live migration rows |
| 11 | Property-specific compliance, tax, insurance limits | Local advisers (template 7) | `config/compliance/` | jurisdictions no longer `null` | Compliance tracking |
