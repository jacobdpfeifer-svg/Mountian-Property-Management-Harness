# For the owner: operations and compliance, in plain English

*Audit completed 2026-10-06. The full details are in REPORT.md.*

## What works

- **The safety rules around prices hold.** When a home has a problem on record (a broken
  hot tub, an inspection due), the system stops changing that home's prices on its own. It
  won't raise prices on a home waiting for inspection. It recommends closing nights at a
  home that is out of service, but it never closes them itself. We tested every combination
  of home condition, night type, and price direction (336 cases). After the fixes below, none
  broke those rules.
- **It never touches bookings or availability in Guesty.** It cannot cancel, move, refund,
  message a guest, or send door codes. Those actions are refused in code. The one optional
  write is creating a cleaning or maintenance task in Guesty, and it stays off unless
  you deliberately turn it on.
- **It never claims a home is "compliant."** The compliance list only tracks whether a
  document is on file, unverified, expiring, expired, or missing.

## What we fixed during the audit

Several problems could have mattered on a real night. Each fix has a test that proves it:

- Fixing the hot tub could quietly clear a separate snowstorm warning on another night.
- A storm warning could crash the daily check, so later homes were never checked.
- Clock mix-ups (UTC vs. Mountain time) could let a home be marked ready while a serious
  problem was still open.
- A home waiting for inspection could show a suggested price below your minimum.
- A mistyped home name on an expense sheet could land on an owner's statement as a general
  charge.
- The compliance lists were missing things the towns and county actually require. These
  include smoke and CO detectors, fire extinguishers, Fraser's occupancy formula (2 per
  bedroom + 4), and Grand County's septic limit. Bookings are now also checked against
  occupancy limits.

## What does not work yet

- **Every operations number is a guess.** That includes clean times, crew size, costs, and
  the chance a clean finishes on time. We have no task records from your cleaners, so nothing
  has been checked against what really happened. On your real summer bookings (April to
  September) we found 24 turnovers, 4 of them same-day, and two days where one crew had two
  homes to turn. We can't say how any of them actually went.
- **Crew shortages are invisible to pricing.** If half the crew calls in sick on a busy
  Saturday, nothing in the system raises an alarm or changes anything. The same goes for a
  task feed that stops updating.
- **Weather warnings never clear on their own.** After a storm, the affected home stays in
  "review every price" mode until a person marks it okay. That is cautious, but someone has to
  know to do it.
- **The connections to cleaning apps aren't proven.** The Turno connection doesn't match
  Turno's own published instructions and would not work. The Guesty and Breezeway
  connections each misread one important field (actual clean time and clean cost). None
  has been tried on a real account.
- **In simulation, the operations features didn't add revenue.** <<OWNER_SIM>>

## What you need to confirm

1. **Which jurisdiction 312 and 300 Northwoods are in:** Winter Park town limits or
   unincorporated Grand County, and which fire district. Until then, no compliance rules
   apply to those two homes at all.
2. **Cloud 9 is set up as Fraser.** Please confirm.
3. **The compliance lists need a person to review them.** All three (Winter Park, Fraser,
   Grand County) were copied from the official websites and have not been checked by anyone
   with authority. Some items need a lawyer's read. Examples: Winter Park's renewal date, and
   each Grand County home's septic capacity.
4. **The operations numbers:** clean time per home, how many cleaners and on which days,
   hot tubs, labor rate, and your management fee percentages.
5. **Which cleaning or task app you actually use,** and a sample export from it, so the
   connection can be fixed and the guesses replaced with real numbers.
6. **The sales pitch.** Its claim that operations is "read-only toward Guesty" should be
   reworded. It never writes prices, availability, or bookings, but it can create a task if
   you turn that on.
