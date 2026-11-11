# Q4 — Readiness states

**Verdict: CHANGE.** Keep the append-only, evidence-cited store and the actor rules. They
are the right boundary. But pricing only distinguishes four conditions, the PM only thinks
in four, and two of the six stored states are ceremony that a phone user will skip or get
wrong. Collapse what the PM sees to four, cut two mandatory steps, and fix three bugs. The
bugs mean the machine as written can wedge a property in a restricted state, or crash a
signal scan.

## What exists

- Stored states: `ready`, `at_risk`, `inspection_required`, `out_of_service`,
  `remediation_in_progress`, `verified_ready` (`src/ops/readiness.py:29-35`). There is also
  an implicit `ready` when a property has no transition rows (`:107-108`, `:164`).
- `EDGES` (`:39-48`):
  - `ready → {at_risk, inspection_required, out_of_service}`
  - `at_risk → {at_risk, verified_ready, inspection_required, out_of_service}`
  - `inspection_required → {verified_ready, out_of_service}`
  - `out_of_service → {remediation_in_progress}` **only**
  - `remediation_in_progress → {verified_ready, out_of_service}`
  - `verified_ready → {ready, at_risk, inspection_required, out_of_service}`
- Actor rules (`:217-228`):
  - Automatic actors (`signal`, `telemetry`, `system`) may only set `at_risk`.
  - `verified_ready` needs a non-generic name, or `sensor_check` with a reading that passes
    the policy check.
  - Every transition must cite an `asset_health_events` row for that property.
  - Recovery is refused while another system has an open critical event (`:229-244`).

## How many states pricing actually distinguishes

`src/compose/__init__.py:433-445` handles readiness as follows:
- `at_risk` and `inspection_required` demote the night to suggest.
- `inspection_required` also caps price at the listed price.
- `out_of_service` and `remediation_in_progress` produce the **same** effect: blocked.
- `verified_ready` and `ready` produce the **same** effect: none.

So there are four effective classes: **OK / Watch / Needs check / Closed**. Six stored
states plus an implicit one is more than a PM needs. The extra distinctions are audit
detail, and the evidence row already records that detail (system, source, note).

## Where the current machine hurts a PM

1. **A three-step recovery from a real outage.** `out_of_service` can only go to
   `remediation_in_progress`, then `verified_ready`, then `ready`. Each step needs its own
   evidence event (`:208-212`). A plumber fixes the pipe at 6 a.m., and the PM has to log
   three transitions, two of which change nothing in pricing.
2. **`verified_ready → ready` does nothing.** Both states have rank 0
   (`readiness.py:37-38`), and compose treats both as unrestricted. The second step exists
   only to make the property "ready" by name.
3. **The routine 7 a.m. action has nowhere to go.** "I walked the house; it's fine" can't
   be recorded from `ready`, because `ready → verified_ready` is not an edge. That is
   correct by design: readiness here is for exceptions. The flow should say so and leave
   routine inspections in the task tool (Breezeway or Guesty Tasks), not invite the PM to
   record them here.
4. **`--actor` is free text** (`src/ops/cli.py:298`). The "named human" invariant is
   whatever string gets typed. Anyone can also type `--actor sensor_check`. That only
   passes if the reading clears the threshold (`readiness.py:221-225`), but nothing ties
   the actor to a person.
5. **Heat counts as "verified" at 50 °F** (`operations.yaml:74`). That is a freeze check,
   not guest-ready. A 50 °F house at 4 p.m. check-in is a complaint. Label it "freeze-safe"
   or raise the bar.

## Bugs found (reproduced in-memory against the worktree code)

- **B1. A future-window risk crashes the signal scan.**
  - Steps: record `out_of_service` for Dec 1–3. On Dec 2, a signal fires for Dec 10.
    `auto_escalate` sees that Dec 10 is governed by `ready` (`:271-273`) and calls
    `transition(at_risk)`.
  - `transition` checks legality against `current_state` (`:214-216`), which is the latest
    row for *any* window. That row is `out_of_service`, and `out_of_service → at_risk` is
    not an edge, so it raises `ReadinessError`.
  - `scan_signal_risk` (`:344`) and the incident action `suppress_auto_price`
    (`src/ops/actions.py:190`) don't catch it. The whole `ops readiness --scan-signals` run
    aborts.
  - Same failure from `inspection_required` or `remediation_in_progress`.
  - Repro: the five lines above; the error is "out_of_service → at_risk is not an allowed
    transition".
- **B2. A refused transition leaves an orphan open critical event that blocks unrelated
  recovery.**
  - `cmd_ops_event_add` commits the event *before* it attempts the transition
    (`cli.py:150-160`).
  - Repro: `event add --system spa --severity critical --state verified_ready` from
    `ready`. The transition is refused, but the spa event stays open and critical.
  - Later, a heat issue goes `at_risk → verified_ready` and is refused with "cannot mark
    ready while critical spa event … remains open". The property is stuck restricted.
    Nothing in the CLI resolves an event directly.
- **B3. The status displays show the latest row, not the state of tonight's night.**
  - `ops readiness` (`cli.py:186`) and the shadow report (`src/ops/shadow.py:153`) call
    `current_state`. Pricing calls `state_for_night`.
  - Repro: an `at_risk` row with window Dec 10–11, recorded Dec 1. On Dec 1,
    `current_state` says `at_risk` and `state_for_night(Dec 1)` says `ready`.
  - The PM and the pricing engine disagree about today.
- Minor: if `current_state` is passed a bare date *string*, rows from that same day are
  excluded (`"2026-12-01T00:00:00" <= "2026-12-01"` is false; `:86-93`). Internal callers
  pass `date` objects today, so this is latent.

## What a PM actually updates at 7 a.m.

Arrivals today and tomorrow. Anything a cleaner, guest, or sensor flagged overnight.
Whether the vendor fixed yesterday's problem. In one phrase: *"Can the next guest stay
here?"*, answered per home, from a list ordered by next arrival. The PM does not think in
"inspection_required vs at_risk". They think "fine / keep an eye on it / someone needs to
look / don't put anyone in it".

## Proposed phone flow (maps onto stored states, keeps every invariant)

**Screen 1 — Today.** One card per home, sorted by next check-in. Each card shows the
night state from `state_for_night`, not `current_state` (this fixes B3):

| Card label | Stored state(s) |
|---|---|
| OK | `ready`, `verified_ready`, or no rows |
| Watch | `at_risk` |
| Needs check | `inspection_required` |
| Closed | `out_of_service` or `remediation_in_progress` (a "vendor on it" chip when the latter) |

Cards also show who set the state, when, and the revenue at risk (already computed,
`readiness.py:283-309`). A grey "sensor stale" chip is a nice-to-have.

**Screen 2 — tapping a card.** It offers at most three buttons, depending on the state:

| Current | Buttons → stored transition |
|---|---|
| OK | **Report a problem** → Screen 3 |
| Watch | **Checked, it's fine** → `verified_ready` · **Needs a look** → `inspection_required` · **Close it** → `out_of_service` |
| Needs check | **Checked, it's fine** → `verified_ready` · **Close it** → `out_of_service` |
| Closed | **Vendor on it** → `remediation_in_progress` (optional) · **Fixed, I checked** → `verified_ready` |

**Screen 3 — Report a problem.** Pick the system from 8 icons (heat, water, hot tub,
power, access/snow, lock, CO/safety, other). Then answer "Can the next guest stay?":
- **Yes, keep an eye on it** → `at_risk` (severity warn)
- **Not until someone checks** → `inspection_required` (warn)
- **No** → `out_of_service` (critical)

Photo and note are optional; date range defaults to "from now, open-ended". One submit.

Every button writes the evidence event **and** the transition in **one DB transaction**
(this fixes B2). The actor is the signed-in user, never a typed string.

### Store changes this needs (none weakens an invariant)

| Change | Why it is safe | Effort |
|---|---|---|
| Add edge `out_of_service → verified_ready` | Still needs a named human or passing sensor, evidence, and no other open critical event. `remediation_in_progress` becomes an optional annotation | S |
| Treat `verified_ready` as terminal OK; stop requiring `→ ready` | Pricing already treats both as unrestricted; the audit trail keeps the verifier | S |
| Check edge legality against the window's governing state (`state_for_night(effective_from)`), and have `auto_escalate` swallow "already restricted" instead of raising | Fixes B1. Automatic actors still can only reach `at_risk` | S |
| Write event and transition atomically; roll the event back on refusal | Fixes B2 | S |
| Show night state, not latest row, in the CLI and report | Fixes B3 | S |
| Actor from authentication, not `--actor` | Makes "named human" mean something. Needs a user identity, which doesn't exist (see Q6) | M |
| Phone UI (PWA over a small API) | New surface | M–L |

The store fixes are about one day of work. The phone flow depends on Q6's auth work.

## Sources

No outside sources. This is a code review of `src/ops/readiness.py`, `src/ops/cli.py`,
`src/ops/actions.py`, `src/compose/__init__.py:420-445`, and
`config/policies/operations.yaml`. B1–B3 were reproduced with in-memory SQLite against
the worktree code on 2026-10-06. The "what a PM thinks" framing is the author's judgment;
no operators were interviewed.
