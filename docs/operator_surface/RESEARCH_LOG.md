# Operator surface research log

Research date: 2026-09-29. This packet is deliberately a design artifact, not an
implementation authorization. Repository facts were read before external research:
`README.md`, locked inputs and architecture, pricing doctrine, autonomy and comp-data
rules, the compose/explain/ingest paths, portfolio YAML, schema, the 2026-09-20
production audit, the 2026-09-25 final testrun audit, and the last 30 commits.

## Non-negotiable local facts

- Guesty is the record of rates. `suggest` writes nothing; `handle` is earned from
  data health, and hard guardrails apply at every level.
- `price_recommendations` already records listed/recommended/floor/ceiling, health,
  guardrail action, dollar-ranked reasons, versions and an `inputs_hash`. The owner
  renderer is presentation-only. A new surface must read these facts, never narrate
  a replacement.
- The current testrun truth is not “the model knows best”: Northwoods exports were
  empty, Cloud 9 was a cold-start four-price calendar, and pacing history remains
  uncalibrated. This argues for visible uncertainty and shadow-mode receipts.
- `summit_haus` and `overlook_ridge` are neighbouring twins; Cloud 9 is separately
  owned. Owner scope is reporting-only today, so memory must never create an
  accidental owner-level pricing channel.

## Track A — seeing prices without drowning

| Source | What it establishes | Verdict here |
|---|---|---|
| [PriceLabs pricing calendar](https://help.pricelabs.co/portal/en/kb/articles/pricing-calendar) | A calendar can expose demand, limits, events, notes and tooltips, but it is a very large control surface. | **Borrow** the explicit limit/event states; **reject** a year grid as the home screen. Three doors need attention routing, not 1,095 cells. |
| [PriceLabs: different prices explained](https://help.pricelabs.co/portal/en/kb/articles/different-prices-on-your-calendar-explained) | Separates raw, customised, bounded, final and last-seen rates. | **Clone the separation**, not the terminology: receipt shows path `floor → listed → recommendation → ceiling` plus the guardrail result. |
| [Guesty pricing-tool precedence](https://help.guesty.com/hc/en-gb/articles/19327541350813-Understanding-pricing-and-pricing-tools-in-Guesty) | Calendar, strategy, optimizer and third-party prices can overlap; same-layer tools override. | **Borrow** the “system-of-record is explicit” warning. This surface is read-only for rates, so it cannot add another precedence layer. |
| [Wheelhouse neighbourhood prices and pacing](https://help.usewheelhouse.com/en/articles/14009220-how-to-view-the-neighborhood-prices-pacing) | Observed vs expected pace and market distribution are useful context. | **Borrow** pace-vs-expected only when the engine has it; **reject** a continuous chart in v1 because current pacing health is thin. |
| [PriceLabs base-price help](https://help.pricelabs.co/portal/en/kb/articles/setting-base-price) | A nudge that requires review is safer than a silent change; history helps sense-check it. | **Borrow** review-before-acceptance and history; **reject** exposing a mutable base-price control, which would duplicate policy governance. |

Finding: vendors solve broad portfolio operations through calendars, settings and
overrides. Mont Luxe has the opposite problem: a tired person must see the ten most
consequential changes, the twin split, and the runs that were deliberately demoted.
That is why it borrows inspection states but not the vendors’ portfolio control plane.

## Track B — explanation that is true

| Source | What it establishes | Verdict here |
|---|---|---|
| [NIST, Four Principles of XAI](https://www.nist.gov/publications/four-principles-explainable-artificial-intelligence) | Explanations must be meaningful and accurate, and systems must disclose knowledge limits. | **Clone.** Render only persisted composer reasons; visibly render weak ceilings, absent evidence and demotion. |
| [NIST AI RMF 1.0](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf) | Trustworthy systems are also reliable, secure, transparent and privacy-enhanced. | **Borrow** the multi-property trust test: pleasant copy never substitutes for an audit trail. |
| [Google PAIR: Explainability + Trust](https://pair.withgoogle.com/chapter/explainability-trust) | Explanation must match the interaction and uncertainty should be communicable. | **Borrow** layered disclosure: one plain sentence first, exact receipt facts on demand. |
| [Application-grounded evaluation of post-hoc explanations](https://arxiv.org/abs/2101.08758) | Fidelity and usefulness must be tested in the real decision context, not presumed. | **Borrow** a receipt regression test: every shown reason must be in `reasons` for that recommendation. |
| [Bias and fidelity of post-hoc explanations](https://arxiv.org/abs/2205.03295) | Post-hoc explainers can vary in approximation quality. | **Reject** a new saliency/LLM explanation layer. The composer already has signed-dollar contribution. |

Finding: “confidence” is not an artistic meter. The receipt uses ordinary language
(`thin evidence`, `comps unavailable`, `health demoted`) tied to actual stored fields.
The exact `inputs_hash`, versions, contributions and reason codes remain available in
the expanded receipt, not silently replaced by prose.
At three doors, exact mechanical provenance is cheaper and more useful than an
approximate explainer built to make a large black-box product feel legible.

## Track C — file drop to durable, useful memory

| Source | What it establishes | Verdict here |
|---|---|---|
| [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) | Allowlists, signatures, size limits, storage controls and malware checks are required; bombs are a real upload threat. | **Clone** the quarantine gate; no “drop and use.” |
| [OWASP Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html) | Extensions/MIME are insufficient; renamed storage and ZIP expansion checks matter. | **Clone** magic-byte validation and generated storage names; **reject** ZIP initially. |
| [OWASP RAG Security](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html) | Document provenance, hashing, source approval and poisoning controls are essential; extensions cannot establish trust. | **Clone** SHA-256, provenance, review and hash verification; **reject** a vector store as a pricing input. |
| [OWASP LLM Prompt Injection](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | PDFs, email and images can carry indirect/multimodal injection; a parser with no tools is the containment pattern. | **Borrow** an optional tool-less extractor only; it may propose claims, never execute or price. |
| [NIST privacy minimization](https://csrc.nist.gov/glossary/term/minimization) | Collect and retain only what is necessary for the stated purpose. | **Clone** a PII rejection/quarantine path and explicit retention/deletion rules. |

Finding: “smart from every file” means an accepted, time-scoped, typed claim with a
measurable effect—not embedding more text. A source file can also produce only a
question, an annotation, or a rejected duplicate; those are honest outcomes.
Unlike a general document platform, this office has no reason to accept arbitrary file
types or to trade a small workflow for an enduring untrusted corpus.

## Track D — personal database versus market database

| Source | What it establishes | Verdict here |
|---|---|---|
| [W3C PROV primer](https://www.w3.org/TR/prov-primer/) | Trustworthy provenance connects entities, activities and responsible agents. | **Clone** the simple file → extraction → claim → confirmation chain. |
| [W3C PROV-O](https://www.w3.org/TR/prov-o/) | Entity, activity and agent are sufficient primitive concepts for a useful lineage. | **Borrow** its vocabulary; do not add an ontology dependency. |
| [SQLite foreign-key support](https://www.sqlite.org/foreignkeys.html) | Foreign keys and transactions can enforce referential integrity. | **Borrow** a small normalized sidecar SQLite schema with FKs enabled. |
| [Microsoft event-sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing) | Append-only histories improve reconstruction but impose real complexity. | **Borrow** append-only claim revisions; **reject** full event sourcing for this three-door workflow. |
| [AWS event-sourcing guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/event-sourcing-pattern.html) | A chronological immutable event record supports traceability and past-state analysis. | **Borrow** immutable status events and as-of reads, not an event-store platform. |

Finding: use a separate local `operator_memory.db`, not a per-owner database and not
an unstructured column in the pricing database. It preserves a clean privacy boundary,
supports one operator tenant, and prevents personal claims being mistaken for market
observations. Scope lives on each claim, not in a database filename.
That is deliberately smaller than an enterprise event store: three humans can review a
claim revision, while still needing a reproducible historical decision.

## Track E — trust, privacy and a three-door office

| Source | What it establishes | Verdict here |
|---|---|---|
| [NIST Privacy Framework](https://www.nist.gov/privacy-framework/privacy-framework) | Privacy risk belongs in ordinary operational risk management. | **Borrow** local risk register and minimisation; do not pretend a local laptop removes risk. |
| [NIST minimization definition](https://csrc.nist.gov/glossary/term/minimization) | Necessary-purpose and bounded-retention are concrete privacy disciplines. | **Clone** short quarantine and deletion choices for files containing guest data. |
| [OWASP upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) | Shared upload surfaces need type/size/content defenses. | **Clone** ownership/permission checks even on localhost. |
| [OWASP RAG security](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html) | Ingestion and provenance remain security boundaries. | **Clone** integrity and approval logs; no silent bulk intake. |
| [OWASP LLM prompt injection](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | Untrusted content plus action-capable tools is an unsafe combination. | **Clone** separation: the browser and extractor have no Guesty credentials or write capability. |

Finding: the present workspace is iCloud Desktop. It is explicitly not a safe source
of truth for private files. The implementation must use a local application-support
directory excluded from sync and git, with OS account access and FileVault as an
operational prerequisite. This is a design requirement, not a claim that encryption is
already deployed.
The small-office difference is material: there is no security team or hosted tenancy to
hide behind, so private bytes and browser authority must remain aggressively local.

## Track F — outside the box

| Source reused as a creative constraint | Idea it tests | Verdict for this office |
|---|---|---|
| [PriceLabs: bounded final price](https://help.pricelabs.co/portal/en/kb/articles/different-prices-on-your-calendar-explained) | Price as a path instead of a lone output number. | **Borrow:** a path fits a printed receipt better than a full calendar. |
| [Guesty precedence](https://help.guesty.com/hc/en-gb/articles/19327541350813-Understanding-pricing-and-pricing-tools-in-Guesty) | A separate decision surface that does not write rates. | **Borrow:** reduces precedence confusion for three operators. |
| [Wheelhouse pacing](https://help.usewheelhouse.com/en/articles/14009220-how-to-view-the-neighborhood-prices-pacing) | Decision clusters versus all-night graphs. | **Borrow:** only where actual pace is healthy; otherwise the receipt says so. |
| [NIST knowledge limits](https://www.nist.gov/publications/four-principles-explainable-artificial-intelligence) | Memory creates questions before it creates a constraint. | **Borrow:** a small team benefits from an explicit “ask” when evidence is weak. |
| [OWASP untrusted-document controls](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | Finder folder rather than connected agent/chat intake. | **Borrow:** the simpler boundary is safer than a clever browser or email bot. |

The resulting seven ideas and their fate are in `ALTERNATIVES.md` and
`STRESS_TESTS.md`. The survivor is intentionally small: a generated local receipt and
an evidence inbox, not a dashboard, chatbot, or remote SaaS.

## Research conclusion

**Borrow, don’t clone:** vendors’ explicit price path, evidence and calendar
precedence; provenance’s source-to-claim chain; security’s quarantine-first intake.
**Reject:** a 365-night dashboard, editable policy controls, automatic document-to-rate
logic, browser-reachable Guesty writes, raw RAG in compose, and multi-tenant hosting.
