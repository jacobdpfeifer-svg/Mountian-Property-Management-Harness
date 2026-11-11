# 05b — Rule pack source check (audit item 2G)

**This is not legal advice.** It compares the transcribed rule packs against the official
pages we could open on 2026-10-06. Nothing here says any property is compliant; every pack
entry stays `unverified` until a person with authority reviews it (`reviewed_by` is null
in all three packs).

Packs checked (worktree `~/wp-price-worktrees/ops-audit`, branch `audit/ops-compliance`):
`config/compliance/winter_park.yaml`, `fraser.yaml`, `grand_county_unincorporated.yaml`.
Checker semantics referenced: `src/compliance/__init__.py` (`_next_fixed_date`,
`deadline_for`, `_check_requirement`, `check`).

## Summary

| Pack | Source URLs | Loaded | Entries that differ from source | Requirements missing from pack |
|---|---|---|---|---|
| Winter Park | 3 | 3 of 3 (summary pages only; town code at amlegal returned 403) | 2 (fire inspection deadline model; sales tax item does not reflect self-collected lodging tax) | 9+ |
| Fraser | 2 | 2 of 2 (ordinance PDF needed local text extraction) | 2 (booking receipt marked optional; liability insurance not on source) | 8+ |
| Grand County (unincorp.) | 2 | 2 of 2 (Section 14.8 PDF is a **2021 superseded version**) | 3 (stale source; fire inspection marked optional; sales tax license not in current regs list) | 8+, including the septic occupancy cap |

The most important single finding: the Grand County pack cites
`DocumentCenter/View/17041/SECTION-148`, a PDF created 2021-03-17. The current Grand County
Zoning Regulations (last amended **July 28, 2026**) renumber the STR rules to **Section 14.7**
and add, among other things, an **occupancy cap tied to the septic (OWTS) design volume + 2**,
a **permit number on every listing** duty, and expanded posting duties. The pack's `max_occupancy: 16`
is right, but the OWTS cap is not modelled at all.

---

## Winter Park (`winter_park.yaml`)

### Per-URL results

| URL | Loads? | Last updated shown | Notes |
|---|---|---|---|
| https://wpgov.com/good-neighbor/ | Yes | None shown | States registration before advertising; registration number "prominently displayed in all advertising"; **all registrations expire September 30**, not pro-rated; $150 fee (Res. 1850); East Grand Fire inspection before registration and at each renewal (up to 25 business days Jul–Oct); quiet hours 10 p.m.–8 a.m.; no overnight parking on any town street Nov 1–May 1; trash not left out overnight. Links Ordinances 552, 574, 624, an info sheet, and the town code. |
| https://wpgov.com/doing-business/rent-your-home/ | Yes | None shown | Thin: business license + remit sales tax; STR must be registered; PM-managed units may operate under the PM's business license; < 31 days (note: ordinance says < 30). |
| https://wpgov.com/our-government/departments/finance/ | Yes | Fees "effective December 1, 2022" (Res. 1946) | Business license $60/yr, which "also functions as a Sales Tax License"; STR registration $150/yr. Winter Park is home-rule and self-collects town tax. |

Alternative / follow-on official sources opened (all from links on the pages above):

| URL | Loads? | Notes |
|---|---|---|
| https://codelibrary.amlegal.com/codes/winterparkco/latest/winterpark_co/0-0-0-1873 | **Failed (HTTP 403)** | Town code itself could not be read. |
| https://wpgov.com/wp-content/uploads/2021/06/O552.pdf | Yes (PDF; text extracted locally) | Ord. 552 (2021) — creates Title 3 Ch. 10. Full STR conditions; see table. |
| https://wpgov.com/wp-content/uploads/2022/05/O574.pdf | Yes (PDF) | Ord. 574 (2022) — penalties: warning / $500 / $1,000 and/or revocation and ban up to 2 years; each day a separate offense. |
| https://wpgov.com/wp-content/uploads/2025/01/O624.pdf | Yes (PDF) | Ord. 624 (adopted Oct 2024) — from **Aug 1, 2025**, registration and renewal need an East Grand Fire inspection "completed within the previous twelve (12) months". |
| https://wpgov.com/wp-content/uploads/2021/09/Short-Term-Rental-Information-Sheet.pdf | Yes (PDF, dated 2021-09-21) | MUNIrevs tasks: STR requirements, **Health and Safety Affidavit**, registration, fee. |
| https://wpgov.com/our-government/departments/finance/sales-tax/ | Yes, "Last Updated July 1, 2024" | Lodging tax 9.0% town (4% general, 3% accommodation, 2% transit & trails), plus state 2.9% and county 1.3%. **Lodging taxes must be filed in MUNIrevs, cannot be filed through Colorado SUTS.** Due the 20th; $15 late fee per late return. |
| https://eastgrandfire.com/fireprevention/str/ and …/fire-life-safety-inspection/ | Yes | Program covers Winter Park, Fraser, and unincorporated Grand County in the district; certificate needed "within the last 12 months"; new certificate on ownership change; $100. No checklist on the page. |

### Per-requirement table

| Pack entry | Source | Status | Note |
|---|---|---|---|
| `str_registration` fixed_date 09-30, listing_match, occupancy_check | good-neighbor | **matches** (renewal) / differs (code text) | Page: all expire Sept 30. Ord. 552 §3-10-4(G) says "term of a registration shall be for 12 months". Page and pack agree on Sept 30; later code amendment not readable (amlegal 403). **Operator/legal review** to confirm. Ord. 552 §3-10-5(A)(1) requires the exact wording "Winter Park Short-Term Rental Registration No. [number]"; the checker only checks that the number appears. |
| `business_license` annual_from_issue | rent-your-home, finance | matches (existence) / renewal unverified | $60 annual. Whether it expires a year from issue or on a calendar date is not stated on any page opened → renewal model `unverified`. PM collective license is allowed (Ord. 552 §3-10-4(F)). |
| `sales_tax_account` none | finance, sales-tax | **differs (incomplete)** | Town lodging tax (9%) is self-collected via MUNIrevs, and the town business license is the town sales-tax license. State 2.9% + county 1.3% go to CDOR and need a **Colorado sales tax license** — the WP pack has no state license item (Fraser and Grand County packs do). |
| `fire_life_safety_inspection` fixed_date 09-30 | good-neighbor; Ord. 624 | **differs** | Ord. 624: the inspection must be "completed within the previous twelve (12) months" when a registration or renewal is submitted. With `_next_fixed_date`, a certificate issued 2026-08-01 gets a deadline of 2026-09-30 and shows `expired` from 2026-10-01 for most of the year, even though nothing is due until the next renewal. The rule is a freshness test at renewal time ("issued ≤ 12 months before the renewal submission"), not an expiry on 09-30. The current model raises false alarms; it does not miss deadlines. Low risk. |
| `responsible_agent` none | Ord. 552 §3-10-5(A)(8) | matches | 24/7, respond within **60 minutes** — confirmed in Ord. 552 (drop "per memo; confirm"). Missing: alternate agent option, notice to town ≥ 7 days before a change. |
| `fireplace_cleaning` annual, optional | Ord. 552 §3-10-5(B)(5) | matches | "Wood-burning fireplaces and stoves … cleaned on an annual basis." |
| `posted_restrictions` | Ord. 552 §3-10-5(A)(7) | matches (partial) | Burn/drought restrictions must be posted. Missing: §3-10-5(E)(1) post **copy of registration and the conditions** in the unit. |
| `liability_insurance` expires_at | — | **not found on page** | No insurance requirement on any Winter Park page or ordinance opened. Fine to track as a business item, but it should not cite these sources. |

### Requirements on official Winter Park sources that the pack is MISSING

1. **Smoke detectors, CO detectors, fire extinguishers installed and operable at all times** — Ord. 552 §3-10-5(B)(4).
2. **Post a copy of the registration and the conditions** in the unit; give conditions to the responsible agent — Ord. 552 §3-10-5(E).
3. **Parking disclosure in every advertisement**: number of on-site spaces, or "no parking provided and no on-street parking permitted" — Ord. 552 §3-10-5(A)(2). Occupant vehicles on-site only; no sleeping in vehicles. (No listing check for this exists.)
4. **High-impact STR (20+ occupants) needs a special use permit before registration** — Ord. 552 §3-10-3(A), §3-10-4(C).
5. **Health and Safety Affidavit** in MUNIrevs — info sheet (2021).
6. **Colorado sales tax license (CDOR) for state + county tax** — finance page and Grand County Sales & Lodging Tax page.
7. Trash per Town Code Title 4 Ch. 10; not left out overnight — Ord. 552 §3-10-5(A)(3), good-neighbor page.
8. Quiet hours 10 p.m.–8 a.m.; no overnight street parking Nov 1–May 1 — good-neighbor page (guest rules; candidate guest-guide content rather than credentials).
9. Property taxes paid — Ord. 552 §3-10-5(C).
10. Registration cannot transfer on sale (new owner must register) — Ord. 552 §3-10-4(B).

Not found on any Winter Park page opened: occupancy formula, caps on number of STRs, insurance minimum, egress rule.

Penalties (Ord. 574): 1st warning; 2nd $500; 3rd+ $1,000 and/or revocation and up to 2-year ban; each day a separate offense; injunctions/eviction of occupants available.

---

## Fraser (`fraser.yaml`)

### Per-URL results

| URL | Loads? | Last updated shown | Notes |
|---|---|---|---|
| https://www.frasercolorado.com/303/Short-Term-Rental | Yes | Ordinance 516 dated **Dec 4, 2024** cited; no page date | Registration via Deckard/Rentalscape; docs list; fire inspection from Feb 28, 2025; smoke/CO/extinguisher/egress; permit number on listing; wildlife refuse; operating license posted at home; fees ($150 + $350/bedroom from Oct 1, 2025); penalties; random inspections. |
| https://frasercolorado.com/DocumentCenter/View/1577/Ordinance-No-488-Short-Term-Registration-Fees | Yes (PDF; WebFetch could not parse, read locally) | Published Aug 25, 2022 | Ord. 488 rewrites §6-8-30 in full (all items below). |

Alternatives opened: Ord. 516 PDF
(https://www.frasercolorado.com/DocumentCenter/View/2124/Ordinance-516-Amending-Chapter-6-Article-8-Short-Term-Rental-Registration) —
loaded, text extracted. Ord. 449
(https://www.frasercolorado.com/DocumentCenter/View/401/Ordinance-NO-449--Short-Term-Rentals) — loaded but scanned
image, **not extractable**. Municode (https://library.municode.com/co/fraser/codes/municipal_code) — **not extractable** (JS shell).
DR 1917 on Fraser site — **failed** (over 10 MB).

### Per-requirement table

| Pack entry | Source | Status | Note |
|---|---|---|---|
| `str_registration` annual_from_issue, listing_match, occupancy_check | page; Ord. 488 §6-8-30(f); Ord. 516 (q) | matches | "annual term … shall commence upon approval of the application and payment of all required fees." Permit number "shall be posted on the rental advertisement platform and/or listing" (Ord. 516). Not transferable on sale (§6-8-30(g)). |
| `proof_of_ownership` | page; Ord. 488 (a)(2) | matches | |
| `operating_license` annual_from_issue | page; Ord. 516 (b) | matches | $40/yr; business license **or** STR operating license. Operating license posted at the home; a PM business license may be posted at the PM office. Calendar vs from-issue renewal not stated → renewal `unverified`. |
| `fire_inspection_certificate` annual_from_issue | page; Ord. 516 (a)(6) | matches | Certificate "dated within the previous 12 months" for registrations/renewals after Feb 28, 2025. |
| `emergency_contact` | Ord. 488 (a)(3), (i) | matches (partial) | 24/7, attend within 1.5 h. Missing: **contact info must be posted inside the unit**; changes updated in platform within 7 calendar days. |
| `parking_plan` | Ord. 488 (a)(4), (n) | matches | Site plan; driveway first, street overflow only if permitted. |
| `booking_tax_receipt` optional | Ord. 488 (a)(5) | **differs** | Ordinance requires a receipt "issued within the 60 days following registration showing collection of all taxes due the Town". It is not "if applicable" in the text. **Operator/legal review** whether it applies to renewals. |
| `posted_registration` annual_from_issue | Ord. 488 (h) | matches | |
| `sales_tax_license` | page | matches | "All STRs must maintain a state sales tax license" via CDOR. Rates on page: Fraser 5% + county 1.3% + state 2.9% + lodging 2% (+0.2% from Jan 1, 2025). |
| `liability_insurance` expires_at | — | **not found on page** | No insurance requirement on the Fraser page, Ord. 488, or Ord. 516. Ord. 449 not extractable. |

### Requirements on official Fraser sources that the pack is MISSING

1. **Smoke detectors installed and operable** — Ord. 488 §6-8-30(l)(1); page.
2. **CO detectors installed and operable** — Ord. 488 (l)(2); page.
3. **Fire extinguisher on every floor, visible or clearly marked** — Ord. 488 (l)(3); page.
4. **Egress doors and windows operable and clear of snow/debris** — Ord. 488 (l)(4); page.
5. **Occupancy limit: 2 per bedroom (assessor bedrooms + extra sleeping areas with a bed) + 4; studios 4** — Ord. 488 (m). The pack sets no `max_occupancy` and no formula, so `occupancy_check` only works if a permit row carries `permitted_occupancy`.
6. **Address clearly marked and visible from the road** — Ord. 488 (k).
7. **Wildlife-edible refuse containers secured inside the home or garage** — page (1st $100, 2nd $200, 3rd misdemeanor).
8. **Contact info posted inside the unit; changes within 7 days** — Ord. 488 (i).
9. **Allow Emergency Services compliance inspection** (9–5, 7 business days' notice); refusal is a revocation ground — Ord. 488 (j), (o)(7).
10. Revocation grounds include unpaid water/wastewater fees and unpaid taxes — Ord. 488 (o).

Pack header says "Fraser was considering STR code amendments in 2025". The page cites Ord. 516 (Dec 2024) as the latest; no 2025/2026 amendment was visible on the page. **Unverified** whether newer amendments exist (municode not readable).

Penalties (Ord. 488 (p)): 1st warning by certified mail, 10 business days to cure; 2nd $500; 3rd $1,000; 4th revocation/suspension up to one year, in 10-day increments within a 12-month rolling period.

---

## Grand County, unincorporated (`grand_county_unincorporated.yaml`)

### Per-URL results

| URL | Loads? | Last updated shown | Notes |
|---|---|---|---|
| https://www.co.grand.co.us/943/Short-Term-Rentals | Yes | None shown | Permit expires one year from approval; fee $100 per advertised occupant; max 16; 7 document items (2 local contacts, safety checklist, annual fire inspection report "if applicable", bear-proof trash, parking plan, liability insurance); fire districts named (East Grand, Grand, Grand Lake). Links "STR Regulations and Restrictions" → Zoning Regulations PDF. |
| https://www.co.grand.co.us/DocumentCenter/View/17041/SECTION-148 | Yes (PDF; text extracted locally) | PDF created **2021-03-17** | **Superseded.** This is the old §14.8. Includes sales tax license item and 1-hour contact; no 16 cap, no OWTS cap, no listing-number duty. |

Alternatives opened:

| URL | Loads? | Notes |
|---|---|---|
| https://www.co.grand.co.us/DocumentCenter/View/27506/Zoning-Regulations | Yes (7.6 MB PDF, text extracted locally) | Cover: "LAST AMENDED July 28, 2026". STR is now **§14.7** (pp. 98–102); §14.8 is now solid fuel burning devices. Amendment log: Res. 2023-4-10 (Apr 20, 2023) "limiting occupancy to 16 and by OWTS". |
| https://www.co.grand.co.us/FormCenter/Short-Term-Rentals-16/STR-Safety-Checklist-97 | Yes | Checklist: 5 lb extinguisher on all floors; address visible; fire pit; smoke alarms in all bedrooms/sleeping areas, interconnected; egress windows and doors operable/unobstructed; CO detectors near sleeping areas and near all gas appliances. |
| https://www.co.grand.co.us/FAQ.aspx?QID=166 | Yes | Septic occupancy described as "design capacity (2 people per bedroom plus 2 additional occupants)"; permits "valid for one calendar year"; contacts respond within 1 hour; Colorado sales tax ID (CR 0100). |
| https://www.co.grand.co.us/1470/Sales-Lodging-Tax | Yes | County lodging tax 2% from Jan 1, 2025; CDOR administers county sales and lodging tax; Colorado sales tax license required; Winter Park town taxes are the exception (self-collected). |

### Per-requirement table (against current §14.7 unless noted)

| Pack entry | Source | Status | Note |
|---|---|---|---|
| `source_urls[1]` SECTION-148 | — | **differs (stale)** | Replace with Zoning Regulations PDF §14.7 (last amended 2026-07-28). |
| `max_occupancy: 16` | page; §14.7(7)(b) | matches | |
| `str_permit` annual_from_issue, listing_match, occupancy_check | page; §14.7(2), (5), (6) | matches | "valid for one (1) year after the date of issuance" (FAQ says "one calendar year" — wording inconsistency; **operator/legal review**). Permit number on every listing (§14.7(6)) — listing_match covers presence. Renewal is **discretionary** and may be denied for complaints, code violations, or **OWTS failure** (§14.7(4)). |
| `sales_tax_license` | 2021 §14.8(E)(1); FAQ; Sales & Lodging Tax page | **not in current §14.7 list**, but confirmed elsewhere | Still required by the county tax page and FAQ (state license for state/county sales + county lodging tax). Keep it, re-cite to https://www.co.grand.co.us/1470/Sales-Lodging-Tax. |
| `emergency_contact` count 2, full-time resident | page; §14.7(7)(a) | matches (partial) | Missing: **respond within 1 hour**; notify county in writing within 5 business days of a change; contacts must be posted in unit. |
| `safety_checklist` annual | page; FormCenter checklist | matches | Checklist items are not tracked individually (see missing list). Annual cadence not stated on the form — `unverified`. |
| `fire_inspection` annual, **optional** | page; East Grand Fire STR page | **differs** | Page lists it "(if applicable)", but East Grand Fire says its program covers **all STRs in the district including unincorporated Grand County**. For homes in the East Grand district (the Winter Park/Fraser area), it is not optional. Make it required when the fire district = East Grand (or Grand / Grand Lake per county page). **Operator review**: confirm which district 312 / 300 Northwoods are in. |
| `bear_proof_trash` | page; §14.7(7)(d) | matches (partial) | Also: garbage plan; street-pickup containers out ≤ 24 h. |
| `parking_plan` | page; §14.7(7)(c) | matches | No on-street parking in county/private road ROW or access easements; shared driveway needs written permission. |
| `liability_insurance` expires_at | page; §14.7(13) | matches | "Owner shall maintain appropriate liability insurance" — no minimum amount stated. |

### Requirements on official Grand County sources that the pack is MISSING

1. **Septic (OWTS) occupancy cap: occupancy limited to the OWTS design volume + 2** — §14.7(7)(b); FAQ restates as 2 per bedroom + 2. The pack only has the flat 16. **P1-level** (fineable, renewal-denial ground, and the checker would report a 14-sleeper on a 4-bedroom septic home as fine).
2. **Smoke alarms, fire extinguishers, CO alarms within 15 ft of each sleeping room** — §14.7(7)(e); checklist adds interconnected smoke alarms and CO near gas appliances.
3. **Posting inside the dwelling**: permit copy, both 24-h contacts, max occupancy with violation statement, parking plan, garbage location/day, quiet times — §14.7(8). Also **give each renter a copy of the permit** at occupancy.
4. **Physical address posted, visible from the street, kept clear of snow** — §14.7(7)(f).
5. **1-hour response** and **5-business-day contact-change notice** — §14.7(7)(a).
6. **Quiet times 7:00 p.m.–7:00 a.m.** — §14.7(10) (stricter than Winter Park's 10 p.m.).
7. **No overnight stays in vehicles, RVs, tents or outdoor structures** — §14.7(11).
8. **Any violation of county/state/federal law is an STR violation** — §14.7(12).
9. Property kept free of garbage/litter — §14.7(9).

Penalties (§14.7(14)): 1st warning; 2nd $500; 3rd $1,000; 4th within 2 years → revocation/suspension up to 1 year by the BOCC; 10 days to cure, and curing does not erase the violation.

Renewal mechanics vs pack: pack `annual_from_issue` matches "one (1) year after the date of issuance".

---

## Renewal mechanics vs pack

| Jurisdiction | Pack | Source says | Status |
|---|---|---|---|
| Winter Park registration | fixed_date 09-30 | Page: all expire Sept 30 (Ord. 552 text: 12-month term) | matches page; code conflict → operator/legal review |
| Winter Park fire inspection | fixed_date 09-30 | Completed within previous 12 months at registration/renewal (Ord. 624) | differs (model as freshness at renewal) |
| Fraser registration | annual_from_issue | Annual term starts on approval and payment (Ord. 488 (f)) | matches |
| Fraser fire certificate | annual_from_issue | Dated within previous 12 months (Ord. 516) | matches |
| Grand County permit | annual_from_issue | One year after issuance (§14.7(2)); FAQ "one calendar year" | matches regs; FAQ wording → review |

## Sources (all opened 2026-10-06)

| URL | Result |
|---|---|
| https://wpgov.com/good-neighbor/ | loaded |
| https://wpgov.com/doing-business/rent-your-home/ | loaded |
| https://wpgov.com/our-government/departments/finance/ | loaded |
| https://wpgov.com/our-government/departments/finance/sales-tax/ | loaded |
| https://wpgov.com/wp-content/uploads/2021/06/O552.pdf | loaded (PDF, text extracted locally) |
| https://wpgov.com/wp-content/uploads/2022/05/O574.pdf | loaded (PDF, text extracted locally) |
| https://wpgov.com/wp-content/uploads/2025/01/O624.pdf | loaded (PDF, text extracted locally) |
| https://wpgov.com/wp-content/uploads/2021/09/Short-Term-Rental-Information-Sheet.pdf | loaded (PDF, text extracted locally) |
| https://codelibrary.amlegal.com/codes/winterparkco/latest/winterpark_co/0-0-0-1873 | **failed (HTTP 403)** |
| https://eastgrandfire.com/fireprevention/str/ | loaded |
| https://eastgrandfire.com/fireprevention/str/fire-life-safety-inspection/ | loaded |
| https://www.frasercolorado.com/303/Short-Term-Rental | loaded |
| https://frasercolorado.com/DocumentCenter/View/1577/Ordinance-No-488-Short-Term-Registration-Fees | loaded (PDF; WebFetch parse failed, read locally) |
| https://www.frasercolorado.com/DocumentCenter/View/2124/Ordinance-516-Amending-Chapter-6-Article-8-Short-Term-Rental-Registration | loaded (PDF, text extracted locally) |
| https://www.frasercolorado.com/DocumentCenter/View/401/Ordinance-NO-449--Short-Term-Rentals | loaded but **not extractable** (scanned image) |
| https://www.frasercolorado.com/DocumentCenter/View/709/Colorado-Tax-Info-STR-DR-1917 | **failed** (over 10 MB fetch limit) |
| https://library.municode.com/co/fraser/codes/municipal_code | loaded but **not extractable** (JS shell) |
| https://www.co.grand.co.us/943/Short-Term-Rentals | loaded |
| https://www.co.grand.co.us/DocumentCenter/View/17041/SECTION-148 | loaded (PDF, text extracted locally; 2021 version, superseded) |
| https://www.co.grand.co.us/DocumentCenter/View/27506/Zoning-Regulations | loaded (PDF, text extracted locally; last amended 2026-07-28) |
| https://www.co.grand.co.us/FormCenter/Short-Term-Rentals-16/STR-Safety-Checklist-97 | loaded |
| https://www.co.grand.co.us/FAQ.aspx?QID=166 | loaded |
| https://www.co.grand.co.us/1470/Sales-Lodging-Tax | loaded |
