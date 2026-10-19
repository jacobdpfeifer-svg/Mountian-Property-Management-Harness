# Depth standard (mandatory, enforced by the reviewer)

Light research fails this pack. A dossier that misses any **MUST** below is sent back.

## Sources

- **MUST** cite every non-obvious factual claim inline with a URL (or a full bibliographic
  reference for books and papers) and an access date.
- **MUST** use at least **40 distinct sources** (R6 and S1: at least 20 new sources plus the
  dossiers they build on). They must span at least **four** of these source classes:
  1. peer-reviewed or academic work (journals such as *Management Science*, *Operations
     Research*, *M&SOM*, *Transportation Science*, *Journal of Revenue and Pricing Management*,
     *Cornell Hospitality Quarterly*; arXiv/SSRN)
  2. canonical textbooks (for example Talluri & van Ryzin, *The Theory and Practice of Revenue
     Management*; Phillips, *Pricing and Revenue Optimization*; Belobaba et al., *The Global
     Airline Industry*; Cross, *Revenue Management*)
  3. vendor technical documentation, white papers, patents (Google Patents, USPTO)
  4. industry-body material: AGIFORS, INFORMS RM&P section, HSMAI, HFTP, IATA, Cornell CHR
  5. company filings and earnings calls (10-K, investor days)
  6. government or official statistical data
  7. practitioner talks, engineering blogs, credible trade press
- **MUST** read primary sources wherever they exist. A blog summary of a paper does not
  replace the paper. If a paywall blocks you, say so and cite the abstract.
- **MUST** mark anything unverified as **UNVERIFIED** and flag data older than 3 years as
  **STALE**. Never invent a statistic, a vendor feature or a citation. A fabricated citation
  fails the dossier outright.
- **MUST** search in several passes: broad, then specific (named methods, named people, named
  papers), then adversarial (critiques, failures, lawsuits, "does X actually work").

## Content

- **MUST** explain mechanisms, not just names. For each method, cover the math or algorithm in
  enough detail that an engineer could implement a first version: objective, inputs, estimation
  method and decision rule.
- **MUST** give quantified evidence of impact where any exists (revenue lift %, A/B results,
  case studies). Say who measured it and whether that party had a conflict of interest, for
  example a vendor reporting its own lift.
- **MUST** map every finding to this engine. Say what it would change, which module
  (`src/pricing`, `src/bookprob`, `src/elasticity`, `src/ceiling`, `src/signals`, `src/comps`,
  `src/scrape`, `proving_ground_exam/`, …) and how we would measure that it helped in
  owner-net-profit terms.
- **MUST** assess transferability honestly. Small inventory (3 homes), thin data, one unit per
  "product", long stays and multi-night constraints, group guests, high prices and fee-inclusive
  display make many airline and hotel methods break down. Say which methods survive and why.
- **MUST** include a "What generic STR pricers miss" note where relevant (hypothesis H2).
- **MUST** end with: (a) a ranked list of recommendations, each with expected impact, confidence,
  effort, data needed and a measurement plan; (b) open questions for the operator; (c) a
  **self-audit table** listing every MUST in this file with PASS/FAIL and evidence (source count
  by class, number of distinct searches run, etc.).

## Process

- Keep a running search log (queries plus what each one yielded) in an appendix.
- Prefer the most recent authoritative sources (2020–2026) and include the foundational
  classics too.
- If you finish early, you have not gone deep enough. Do another adversarial pass and look for
  what contradicts your findings.
