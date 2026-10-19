# S1: Synthesis, gap matrix and profit-ranked roadmap

Output: `docs/research/deep_2026-10/S1_synthesis.md`
Inputs: R1–R7 dossiers and their reviews.

## Deliverables

1. **Executive summary** (one page). What mature RM industries know that we don't. Where
   generic STR pricers are weak. Which data matters most. What to build first.
2. **Capability gap matrix.** Rows are capabilities: demand forecasting, unconstraining, pickup
   and pace, elasticity / WTP learning, competitor intelligence, forward market occupancy,
   LOS / gap control, group / displacement, overbooking / cancellation, price experimentation,
   simulation / validation, human override, fairness / reference price, data-stream breadth and
   value ranking. Columns: airline best practice | hotel best practice | other industries | generic
   STR pricers | **our engine today** (cite repo paths) | gap severity | transferability.
3. **Hypothesis verdicts** H1–H7 with the evidence.
4. **The specialist thesis, stated precisely.** The 3–5 edges a Winter Park / mountain specialist
   can own, and for each one why it is defensible.
5. **Roadmap** ranked by expected owner-net profit per unit effort. For each item: expected
   impact range, confidence, prerequisites, owning module, proving-ground test, field
   measurement, and kill criteria. Respect current constraints: the scraper is binding, data is
   thin, the field MDE is about 33%, and the canary is inactive.
6. **What not to do.** Methods that look sophisticated but will not pay at our scale, with the
   reasons.
7. **Build prompts.** Draft 2–4 concrete, self-contained build prompts for the top roadmap items,
   in the style of `docs/prompts/*.md`, ready to hand to an implementation agent.

Resolve contradictions between dossiers explicitly. Do not average them away.
