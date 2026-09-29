# Alternatives: test the sketch before building it

The starting sketch—minimal dashboard plus drag-and-drop—is sensible as a first
sentence, but fails as an operating model. It asks one screen to be a calendar, a
trust report, a policy editor, a file room and a learning system. At three doors that
is already more interface than decision.

## Serious alternatives

| Option | What an operator actually uses | Strength | Failure | Decision |
|---|---|---|---|---|
| A. Calendar dashboard + drop zone (starting sketch) | A 365-night grid, filters, price-detail drawer, upload widget. | Familiar; direct comparison to Guesty/PriceLabs. | Makes every night look equally important, invites parallel manual overrides, and turns memory into an attachment pile. | **Reject as primary surface.** Keep a date-level detail view only as a later drill-down. |
| B. Local run receipt + Finder evidence inbox | A dated, printable one-page HTML receipt after each run; drag one file into a watched inbox; review proposed claims in the next receipt. | Gives Sunday a calm answer and keeps files local; works with no server and makes `handle` after-the-fact legible. | Requires a tiny local watcher/parser and a review step; less instantly flashy. | **Recommend.** This is the thin slice. |
| C. “Two-pane court” | Engine case on the left, operator objections on the right, memory files as exhibits. | Makes provenance and disagreement obvious. | Too theatrical at 10pm; “objection” can become a shadow price-control system. | **Borrow** the exhibit/provenance metaphor for the receipt’s claim cards; reject the full interaction model. |
| D. Memory as questions only | Files can create owner questions and reminders, never any engine feature. | Safest possible anti-RAG design; useful even with messy files. | Cannot meet the required, testable “next run differs because this file exists” loop. | **Keep as a claim outcome**, not the only memory mode. |
| E. Write-only memory / read-only prices | Operators learn prices only in Guesty; this app accepts and confirms memories. | No chance of a second calendar or browser write path. | Fails the price-window job and hides health demotions. | **Reject alone.** Price receipt remains read-only; Guesty remains the calendar. |
| F. SMS/audio daily brief | Three high-impact changes read aloud or sent as text. | Good for a car/phone; drives attention to a receipt. | Loses proof, privacy and the exact price path; poor place for approval. | **Defer.** Later optional notification may link to the local receipt, never become the source of truth. |
| G. Index cards per decision cluster | Cards represent a short date span/change cluster, not a night. | Good cognitive unit for a small portfolio; exposes twins. | Clustering can conceal an important outlier. | **Borrow.** The receipt contains a few ranked clusters with expandable per-night rows. |
| H. One-file-per-week ritual | Intake throttled so every file gets care. | Prevents a screenshot flood. | Blocks time-sensitive owner instruction and makes “files make us smarter” arbitrary. | **Reject hard quota.** Use a queue, duplicate detection and a 20-file/day safety throttle instead. |

## Seven weird ideas, stress-tested

1. **No website:** Finder is the drop zone; a generated HTML receipt is the price
   window. **Survives** because the operator already has a laptop, and it keeps Guesty
   credentials out of the browser.
2. **Decision-cluster index cards:** one card for “Christmas Northwoods moved” rather
   than nine date cells. **Survives with an outlier rule:** any guardrail, weak ceiling,
   twin split, or ≥$100 move becomes its own card.
3. **Memory may only create questions.** **Fails the mission alone; survives as a safe
   claim class.** It is useful when a file is ambiguous or asks for an owner decision.
4. **Two-pane court:** engine/opinion/exhibits. **Fails:** ceremonial, too much screen,
   and encourages a debate over every number. The receipt retains only the “exhibit”
   link for an accepted claim.
5. **Prices as a path rather than a number:** `floor → listed → recommendation → ceiling`.
   **Survives.** A number is a conclusion; the path explains bounds and deference.
6. **One file per week.** **Fails:** an event PDF or explicit owner instruction can be
   time-sensitive. Queue limits are operational protection, not a learning philosophy.
7. **No approval in this app:** approvals occur in Guesty, while the receipt records
   acknowledgement. **Survives for the thin slice.** It removes a browser-to-Guesty
   route and honors Guesty as record. A later local approval flow may only call the
   existing guarded backend, never Guesty from the browser.

## Why the boring-looking survivor wins

The recommended system is not “a dashboard, but smaller.” It is a local paper trail
that happens to render in a browser:

```text
daily engine run ──► local Run Receipt.html ──► print / read / open Guesty
                         │
                         └──► ~/.MontLuxe/Evidence Inbox/  (one dropped file)
                                      │
                                  quarantine + extract
                                      │
                         proposed claims on next receipt
                                      │
                              human confirms / rejects
                                      │
                      deterministic memory feature builder
                                      │
                     next run records memory-set hash + effect
```

It is better for this portfolio because it uses the unit that matters—a decision,
not a SaaS object—and because it can be useful with zero memory files. At thirty doors,
the same receipt model can gain filters, inbox assignment and a compact local web app;
it should not gain a new pricing authority ladder.
