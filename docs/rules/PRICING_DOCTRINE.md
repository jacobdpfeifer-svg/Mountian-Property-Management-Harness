# Pricing Doctrine — Winter Park Luxury Portfolio

Enforcement-first policy. Numbers that the engine reads live in `config/policies/`. This document is the human-readable source of intent.

## Objective

Maximize **RevPAN** (revenue per available night). Do not chase occupancy by dumping rates on peak nights. Do not leave ceiling on the table when demand is strong.

## Authority

**Auto-push within guardrails** (`handle`), but only when the data-health gate grants
it. Autonomy is computed per run, never configured per run. See `AUTONOMY.md`.

## Ceiling

Each property has its own realistic revenue ceiling: the high end of what *this* unit
has achieved on comparable nights (season x day-of-week). Comp evidence adjusts it by
at most `ceiling.comp_blend_weight`, and only when comps are fresh and cover enough of
the set; competitor rates inform the number, they do not set it.

**Cross-season fallback is forbidden.** With 6-12 months of history, whole-history
statistics are ~98% peak-ski. Applying that to a shoulder night licenses a move the
night cannot support — measured at a median +22.4% (max +43.6%) on early-December
nights before this rule existed. Thin seasonal history falls back to the *seasonal
anchor* (`base_ceiling_rate x season_multiplier`), and the resulting ceiling carries a
confidence below 1.0 which blends it toward that anchor and caps autonomy.

Booked prices are censored — you only observe prices that converted — so a ceiling
built purely from own history encodes last season's underpricing. That is why comp
evidence and the seasonal anchor both enter the number.

## Leakage we hunt

1. **Peak underprice** — high demand signal + listed well below ceiling.
2. **Shoulder over-discount** — soft demand but listed below the productive shoulder floor.
3. **Orphan gap nights** — 1-2 empty nights between bookings. **Min-stay is the first
   lever, price is the second**: a 2-night hole cannot be sold at any price while a
   3-night minimum is in force. The scanner emits a `min_stay_action` alongside the
   gap-fill discount; compose persists `recommended_min_stay` and may push relaxed
   `minNights` when autonomy is `handle` and `leakage.orphan_gap.push_min_stay_relaxation`
   is true.
4. **Channel mix drift** — deferred until channel-level data exists.
5. **Invisible in comps** — flag for manual review when rate band never overlaps curated comps.

## Dynamic minimum stay

Standing min-nights come from `min_stay_rules` in policy: a season × lead-time lookup
table (far-out / peak → higher; close-in → lower). Gap overrides temporarily relax the
standing rule for orphan windows. Exact buckets are **owner-tunable** — confirm before
trusting auto-push of Guesty `minNights`.

## Per-person framing

`recommended_price / max_occupancy` is display-only (CLI + `per_person_nightly` column).
It never enters RevPAN, ceiling, or booking probability.


## Elasticity

Elasticity is **by season**, not one global number, and it is load-bearing: price is
chosen by maximizing `P x P(book|P)` over `[floor, ceiling]`, so beta determines the
answer. Luxury peak ski inventory is inelastic (`-0.65`); shoulder is elastic
(`-1.70`). Demand is modelled as linear around a reference price, which yields a real
interior optimum — a constant-elasticity form is monotone in price and degenerates to
"always charge the floor" or "always charge the ceiling".

Pacing behind the portfolio norm scales elasticity up. First-party inquiry conversion
softens upward moves when it is clearly weak at the quoted rate.

## Explainability

Every recommended price must show its top 2–3 contributing reasons from the fixed taxonomy. No black-box numbers.

The default owner/CLI surface is a **price range**, an honest **evidence-stream count**, and **plain-English drivers** (`src/explain/present.py`). Dollar ranking stays in `select_top_reasons`. Internal strings (beta, SQI, bucket, sample n=) remain on each reason as `technical_message` for operator debugging (`wp-price recommend --technical`).
