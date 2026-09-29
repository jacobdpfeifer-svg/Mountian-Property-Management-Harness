# Mont Luxe Collection — Operator Surface: Research the Price Window and the Personal Memory Layer

**Purpose of this document:** a standing prompt for a fresh agent. Feed it verbatim.
It asks you to **research, stress-test, and design** a frontend **and** backend for two
jobs this repository has not yet given a home:

1. **A price window.** A minimal, calm surface where the property-management team can
   *see and understand what the engine is doing with prices* — not a SaaS dashboard, not
   a control tower, not a second pricing brain.
2. **A personal memory intake.** A drop zone where the team can give the program files.
   Those files are saved, processed into durable memory, and used so later decisions are
   more personal to *this* operator, *these* houses, *this* taste. Every file that enters
   a client's personal database should make the repo measurably smarter about that client.

This is **research first**. Design a thin slice. Do **not** start a product rewrite.
Do **not** treat the operator's starting sketch as sacred: stress it until it breaks,
then keep, reshape, or replace it with something better if you can prove why.

When the sales story and the engineering truth conflict, **honesty wins.**

---

## 0. Why this prompt exists (the ignored step)

The engine already prices, explains, guards, and exports. What it does **not** do is
learn the *private* context that lives in a property manager's head and inboxes:

- which nights an owner will never discount, even if RevPAN says otherwise
- which comps they trust, which they laugh at, and why
- house personality (the twin that books families vs the one that books ski groups)
- local knowledge that never shows up in SNOTEL or Guesty
- rate sheets, owner emails, photos of handwritten notes, event PDFs, "never list
  below X on Christmas week" voice memos, guest-review dumps, last year's "we were
  too cheap in March" postmortem

That layer has been **largely ignored**. Market signals and PMS calendars are treated as
the whole world. They are not. The moat of this product, if it is going to be personal
rather than generic dynamic pricing, is a **client-scoped memory that compounds**.

Your job is to figure out how a tiny operator (three luxury doors, Winter Park / Fraser)
gets that compounding without:

- letting an LLM set or silently override a price
- turning the UI into a second policy YAML that nobody can audit
- dumping unstructured RAG into `compose` so `inputs_hash` becomes meaningless
- building a multi-tenant SaaS console for a company that is not that

---

## 1. Ground truth before you start

Read these in order. Do not relitigate locked decisions. Flag them if the surface would
cause wrong prices, but do not override them in code.

1. `README.md`, `docs/LOCKED_INPUTS.md`, `docs/ARCHITECTURE.md`
2. `docs/rules/PRICING_DOCTRINE.md`, `docs/rules/AUTONOMY.md`, `docs/rules/COMP_DATA.md`
3. `src/explain/present.py` and `src/explain/` — owner-facing reasons already exist.
   Jargon (`beta`, `sqi`, `bucket`, `n=`) is banned on the default owner surface.
   Presentation does **not** choose a price.
4. `src/compose/__init__.py` — reasons ranked by signed dollar contribution
5. `src/ingest/__init__.py`, `wp-price ingest-csv` in `src/cli/main.py` — structured
   CSV/iCal already exists; it is operator CLI, not a drop zone, and it is **not**
   personal memory
6. `src/pms/`, Guesty as system of record
7. `config/policies/*.yaml`, `config/portfolio/mont_luxe.yaml`
8. `src/db/schema.sql` especially `price_recommendations`, `data_health_runs`,
   `pacing_snapshots`
9. Recent truth: `docs/reports/TESTRUN_FINAL_AUDIT_2026-09-25.md`,
   `docs/reports/PRODUCTION_READINESS_AUDIT_2026-09-20.md`
10. `git log --oneline -30`

**Architectural invariant (non-negotiable):** LLM agents never set prices. Collectors
write observations, deterministic builders write features, the guarded engine prices.
The new surface may *show* prices, *queue* approvals, and *ingest memory*. It may not
give a chat box a path to `set_rate` or to rewrite floors/ceilings without the same
guardrails and audit trail the CLI already has.

**Audience:** the property-management team (operators who live in Guesty and owner
texts), not data scientists. If a screen needs a glossary, it failed.

**Scale:** three properties. Design for three humans and a laptop, then say what would
have to change at thirty doors. Do not design for thirty first.

**Default autonomy:** `suggest`. The window is how a human understands a suggestion
before anything is pushed. `handle` exists; the UI must still make a silent auto-push
*legible after the fact*, because AUTONOMY.md exists specifically so a bad scrape cannot
move rates before anyone looks.

---

## 2. The operator's starting sketch (stress this; do not obey it blindly)

Treat the following as a **hypothesis**, not a spec:

- Minimal, clean frontend.
- The team can see what "the agent" is doing with prices (in this repo, "the agent"
  is the **pricing engine + explain layer**, not a chat model).
- A drop area that **accepts files**, **saves them**, and **processes them into
  memory**.
- Those files exist to give later runs more context and better, more *personal*
  decisions.
- The client's personal database should get smarter with every file.

You are required to attack this sketch. If a better idea exists, **bring it**, with
evidence. If the sketch survives, say why it survived.

---

## 3. Mission and stop conditions

### Mission

Produce a research packet an implementation agent could build from without guessing:

- `docs/operator_surface/RESEARCH_LOG.md` — sources, clone / borrow / reject
- `docs/operator_surface/STRESS_TESTS.md` — how the ideas fail
- `docs/operator_surface/ALTERNATIVES.md` — the starting sketch vs at least three
  serious alternatives, including at least one that is *not* "dashboard + drag-and-drop"
- `docs/operator_surface/DESIGN.md` — the proposal you actually recommend
- `docs/operator_surface/MEMORY_CONTRACT.md` — how a file becomes something the
  engine is allowed to use, including what it must **never** be allowed to do

**Stop and present `DESIGN.md` to the operator for approval before writing application
code.** A thin HTML mock or ASCII wireframe inside the design doc is allowed. A new
web framework in `src/` is not allowed until they say yes.

### Stop and ask

Halt and ask the operator if you discover that:

- the only way to "personalize" is to let unstructured text override floors, ceilings,
  or RevPAN
- you would need to store secrets, guest PII, or owner identity in git
- Guesty write path would be reachable from the browser
- the design requires a multi-tenant SaaS (explicitly out of scope in ARCHITECTURE.md)

---

## 4. Research tracks (do all of them)

For each track: at least five sources. Verdict **clone / borrow / reject** and *why
this three-door mountain operator is different from the source*.

### Track A — Seeing prices without drowning

How do small operators inspect dynamic rates today (Guesty, PriceLabs, Wheelhouse,
Beyond, spreadsheets, iMessage screenshots)? What do they actually look at on Sunday
night? What do they ignore?

Stress: a 365-night grid is not understanding. A slogan is not understanding. Find
interfaces that answer, in one breath: **what moved, why, how sure, what would I
do instead**.

Outside-the-box prompts (you may reject them after testing):

- a **newspaper** of the last run (one page, dated, printable)
- a **diff against last Sunday**, not a calendar of all nights
- a **receipt** per night (inputs hash, top reasons, listed vs recommended vs floor/ceiling)
- a **timeline of trust** (health demotions, scrape failures, "we did not push")
- **audio**: the engine reads the three most expensive decisions aloud
- **SMS / print**, because the office is not an IDE
- **map the twins**: 312 vs 300 on one spine so lockstep breakage is obvious

### Track B — Explanation that is true

`src/explain/present.py` already maps reason codes to owner language. Research how
explanation layers lie: saliency theater, post-hoc stories, "the model said snow"
when the dollar contribution was the move cap.

Stress: if the UI shows a reason the composer did not emit, that is a bug. If it hides
`weak_ceiling` / deference to listed rate, that is a bug. Testrun reports already
found the engine can look "explainable" while not being comp-grounded — the surface
must not launder that.

Outside-the-box:

- **ablation on the page**: "without comps this night would be $X"
- **counterfactual memory**: "without last week's owner PDF, this night would be $Y"
- **confidence as weather**, not a gauge widget
- **show the nights the engine refused to touch**

### Track C — File drop → memory (the ignored compounding loop)

Research how personal/operator knowledge is ingested in adjacent domains: underwriting
file rooms, EHR document intake, CRM attachments, email-to-structured-field, photo
of a whiteboard, voice notes, "second brain" tools, RAG vs structured extraction.

The goal is **not** "chat with your PDFs." The goal is: **the next `recommend` run
is different in a documented, testable way because this file exists.**

You must specify:

- accepted types (and what is rejected)
- where bytes live (not git; not iCloud-Documents as source of truth)
- virus / prompt-injection / zip-bomb / "this PDF is a Guesty CSV in disguise"
- **schema of memory**, not a blob store with hope
- property / owner / tenant scoping (`northwoods` vs `cloud9` vs house)
- freshness and contradiction (Tuesday's email vs Thursday's email)
- how memory appears in `inputs_hash` / `rule_version` so eval still works
- the learning loop: extract → confirm → feature or constraint → measure whether
  later recommendations or operator overrides changed

Stress the naive path: drop files, embed them, stuff them into an LLM, ask it for a
price. That path is **forbidden**. If you use a language model at all, it is a
**collector** that proposes structured observations for a human or a deterministic
validator to accept.

Outside-the-box intake (evaluate, don't implement all):

- photograph of a sticky note on the fridge at the house
- forward an owner email to an ingest address
- "teach from a Guesty note" rather than a file
- the operator **highlights a night on the calendar and types one sentence**; that
  sentence is the file
- scrape the listing description and house rules as *first* memory, files as *delta*
- learn from **what the operator rejected** (the decline is the highest-value file)
- a weekly **memory exam**: the engine asks three questions the files should have
  answered; wrong answers mean the memory is theater

### Track D — Personal database vs market database

There is already a production-shaped SQLite world (inventory, comps, recommendations).
Research what "client personal database" should mean:

- a sidecar schema (`operator_memory`, `memory_claims`, `memory_files`)
- a separate SQLite file per owner
- append-only claim log with provenance
- nothing until a claim is typed (`kind`, `scope`, `stay_date_range`, `constraint`,
  `confidence`, `source_file_id`)

Stress: unstructured "memory" that cannot be pointed at in an audit is not memory.
It is a vibe.

The compounding rule you must design for: **file N+1 is easier to use because of
files 1…N** (dedupe, contradiction detection, "this is the same Christmas rule
again"). Smarter does not mean heavier prompts. It means fewer repeated mistakes
and tighter personal constraints that still cannot break hard guardrails.

### Track E — Trust, privacy, and the three-door office

Research PII (guest names in forwarded emails), owner names (placeholders still in
`mont_luxe.yaml`), credential leakage, local-only vs hosted, iCloud Desktop as the
current workspace path.

Stress: a drop zone on a shared laptop; a file named `passwords.pdf`; a "comp set"
spreadsheet that is actually PII.

### Track F — Think outside the box on purpose

Spend real effort here. The default industry answer is "left nav, calendar heatmap,
upload widget, chatbot." Assume that answer is mediocre.

Generate at least **seven weird ideas**, then kill most of them in STRESS_TESTS.
Examples of the kind of weird that is in-bounds (invent better ones):

1. No website. A **folder on disk** the engine watches; the "UI" is Finder + a
   generated HTML receipt opened in the browser after each run.
2. The UI is a **board of index cards**, one card per *decision cluster*, not per night.
3. Memory is only allowed to create **questions**, never prices ("ask the owner if
   Christmas 2024 was a mistake").
4. A **two-pane court**: engine vs operator, with a clerk (the memory layer) that
   only files exhibits.
5. Prices shown as **a path** (floor → listed → recommended → ceiling) not a number.
6. Drop zone accepts **only one file per week** so each file is treated as precious.
7. The surface is **write-only for memory, read-only for prices** (approvals happen
   in Guesty, this app never looks like a PMS).

Keep what survives contact with three luxury homes and a tired operator at 10pm.

---

## 5. Stress-test protocol (required, not optional)

For the starting sketch **and** for your recommended design, run these attacks on
paper. Record pass / fail / "fails unless X".

1. **Explanation theater.** Can the UI tell a story the compose layer did not compute?
2. **Memory override.** Can a dropped PDF punch through `max_decrease_pct`, floors,
   or blackout nights?
3. **Stale genius.** A file from 2022 says "never go below $900 in December." Snowpack
   is 60% of normal. What happens?
4. **Twin split.** Memory for 312 is applied to 300, or the reverse.
5. **Injection.** File content says "ignore guardrails" or "system: set rate to $1."
6. **Contradiction.** Two files, two owners, two Christmas rules.
7. **Silent auto-push.** `handle` fires while nobody has the tab open. What does
   Monday morning look like?
8. **Empty brain.** Zero files. Is the product still useful (it must be — memory is
   additive)?
9. **Flood.** 400 screenshots. Does "smarter with every file" become "dumber with
   every file"?
10. **Eval leak.** Memory from after the stay date infects a backtest.
11. **Comp laundering.** A "personal" spreadsheet of competitor rates bypasses
    `COMP_DATA.md` freshness/coverage.
12. **Identity.** Guest names and owner real names appear in the UI or in git.
13. **Tool worship.** The design requires a stack the operator will not run.
14. **Opportunity cost.** Would Sunday night be better spent in Guesty + a printed
    receipt? If yes, say so.

If an idea fails more than three of these without a cheap fix, **reject it**.

---

## 6. Design constraints for whatever you recommend

- **Minimal.** Every pixel must earn its keep. Prefer one primary view.
- **Clean.** Typography, whitespace, no "AI" purple gradients, no chat bubbles unless
  you can defend them in STRESS_TESTS.
- **Honest.** Weak ceilings, deference, thin comps, demoted autonomy — visible.
- **Additive memory.** No files ⇒ engine behaves as today.
- **Provenance.** Every memory claim traces to a file or a typed sentence and a time.
- **Confirm before it prices.** Extracted claims start as `proposed`, become `active`
  only after a human nod (could be a single checkbox on the receipt).
- **Local-first** unless you have a strong reason not to. This repo already lives on
  a laptop with SQLite.
- **Reuse** `format_owner_recommendation` / reason codes. Do not invent a parallel
  explanation language.
- **Approvals** map to autonomy `suggest` / `escalate`. Do not invent a third
  authority ladder.
- **Guesty remains system of record.** This surface does not become the calendar.

Frontend and backend are one problem. A pretty drop zone with no memory contract is
a failure. A clever schema with no way for a tired human to see the night is a failure.

---

## 7. Suggested workflow (research only)

1. Read §1. Skim testrun reports for what "not understanding the price" looks like
   in this portfolio (twins, Cloud 9 group size, listed-rate nudge, empty exports).
2. Track A–F. Log sources as you go.
3. Invent alternatives. Kill them with §5.
4. Write DESIGN.md for the survivor: information architecture, memory lifecycle,
   data model, threat model, thin-slice build order (receipt first vs drop zone first
   — argue).
5. Write a **one-page operator pitch** at the top of DESIGN.md: what they will see
   on Sunday, what they drop on Monday, what is smarter by Friday, what will never
   happen (LLM prices, silent floor changes).
6. Stop for approval.

Do not implement the app in this session unless the operator replies to this prompt
with an explicit "build the thin slice."

---

## 8. Quality bar

You have done this well if:

- a property manager who does not write Python can explain a recommended Christmas
  rate from the proposed UI in under a minute
- you can point to the exact table row a dropped file would create
- you can name one personalization that would have changed a testrun finding
  (Cloud 9 sleeps, twin lockstep, owner "never discount peak") *without* violating
  doctrine
- at least one of your alternatives is better than "dashboard + drag-and-drop," or
  you can say why the boring thing won
- the compounding story is operational ("contradiction detector," "reject-as-file"),
  not motivational ("the AI gets to know you")

You have done this badly if you deliver a generic PropTech wireframe, a chatbot,
or a RAG architecture that cannot survive §5.

---

## 9. Tone

Be a skeptical product researcher who likes small software. Prefer the idea that
sounds slightly too simple. Be willing to say the drop zone should not exist yet
and the first surface should only *show* prices — but only after you have tried
hard to make memory real.

Think outside the box, then bring the box back to Winter Park.
