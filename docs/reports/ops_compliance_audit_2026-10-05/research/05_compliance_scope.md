# 05 — Colorado mountain compliance scope (Stage 5, question 5)

**This is not legal advice.** It lists what official pages we opened on 2026-10-06 say a
manager can be fined or delisted for in Winter Park, Fraser and unincorporated Grand County,
and whether the compliance register tracks it. Anything that turns on interpretation is
marked **operator / legal review**. Status labels: a row is `unverified` unless we
confirmed it on an official government page we opened (URL given). "Confirmed on page" means
the page says it. It does not mean the register or any property meets it.

## Verdict: CHANGE (keep the design, change the contents)

- **Keep** the architecture: per-jurisdiction rule packs, document and deadline tracking, five
  statuses, and never saying "compliant". The null-jurisdiction case is surfaced as `missing`
  (`src/compliance/__init__.py` `check()`), not dropped silently.
- **Change** the packs. They track paperwork (permits, licenses, contacts) but leave out the
  **life-safety equipment** every source requires (smoke/CO alarms, extinguishers, egress),
  **occupancy formulas** (Fraser 2/bedroom + 4; Grand County **septic design volume + 2**),
  **in-unit posting** duties, and Winter Park's **parking line in every ad**. The Grand County
  pack cites a **superseded 2021** section; the current text is §14.7 of the Zoning Regulations
  (last amended 2026-07-28). Detail: `05b_rule_pack_source_check.md`.
- **Do not replace.** No official source suggests a different model; the gaps are missing rows,
  not a wrong approach.

### P1 candidates (fineable and not tracked; the register shows nothing)

1. **Grand County septic occupancy cap** (OWTS design volume + 2). Not modelled. The
   `occupancy_check` compares only against 16 or a permit's `permitted_occupancy`. OWTS failure is
   also a ground to refuse renewal.
2. **Smoke/CO/extinguisher/egress** in all three jurisdictions. No pack row. Winter Park
   requires them "operable at all times" (Ord. 552). Fraser and Grand County list them in code.
3. **Fraser occupancy formula** (2 per bedroom + 4; studios 4). No `max_occupancy` in the Fraser pack.
4. **Winter Park ad content**: the parking-spaces statement and the exact registration-number
   wording are required in every advertisement. The checker only tests whether the number appears.
5. **Winter Park state sales tax license**. The WP pack has a generic `sales_tax_account` and no
   CDOR license row, but state 2.9% and county 1.3% go to CDOR, separate from the town's
   self-collected 9% lodging tax.
6. **Grand County fire inspection is marked `optional`**. East Grand Fire says its program covers
   all STRs in the district, including unincorporated Grand County.
7. **Two homes (312 / 300 Northwoods) have `jurisdiction: null`**. The checker reports `missing`,
   which is visible, but no rule applies to them until an operator sets the field.

## Matrix: what you get fined or delisted for

Legend: Covered = yes / partially / no, with the pack line. Penalty as stated on the source.

### Taxes and licenses

| Obligation | Covered by register | Penalty stated | Status / source |
|---|---|---|---|
| Colorado sales tax license (state + county sales, county lodging) | **Partially.** Fraser `sales_tax_license`; Grand County `sales_tax_license`; Winter Park **no** (only `sales_tax_account`) | Not stated on pages opened. Fraser lists unpaid taxes as a revocation ground (Ord. 488 §6-8-30(o)(5)). | Confirmed: https://www.co.grand.co.us/1470/Sales-Lodging-Tax ("you must hold a Colorado Sales Tax License"); https://www.frasercolorado.com/303/Short-Term-Rental. CDOR's own pages (tax.colorado.gov) **returned 403**, so CDOR penalties/renewal cadence are `unverified`. |
| Grand County lodging tax 2% (from 2025-01-01), via CDOR | Partially (implied by sales tax license row; no remittance tracking) | Not stated | Confirmed: https://www.co.grand.co.us/1470/Sales-Lodging-Tax |
| Winter Park town lodging tax 9% (4% general + 3% accommodation + 2% transit & trails), filed **in MUNIrevs, not SUTS**, due the 20th | Partially: WP `sales_tax_account` (evidence only, no filing cadence) | **$15 late fee per late return** | Confirmed: https://wpgov.com/our-government/departments/finance/sales-tax/ (last updated 2024-07-01) |
| Winter Park business license ($60/yr; also the town sales-tax license) | Yes: WP `business_license` | Not stated separately | Confirmed: https://wpgov.com/our-government/departments/finance/ |
| Fraser business or STR operating license ($40/yr, posted) | Yes: Fraser `operating_license` | Within STR penalty ladder | Confirmed: Fraser page; Ord. 516 |
| Fraser booking receipt showing town taxes within 60 days of registration | Yes, but marked `optional` (source does not say optional) | Within ladder | Confirmed: Ord. 488 PDF (https://frasercolorado.com/DocumentCenter/View/1577/Ordinance-No-488-Short-Term-Registration-Fees). **Operator / legal review**: does it apply at renewal? |
| Marketplace-facilitator (Airbnb/VRBO) collection of state/local tax | No | — | `unverified`: CDOR pages returned 403. **Operator / legal review**: which taxes the platforms remit vs the manager, especially WP town tax (MUNIrevs). |

### STR permits, caps and listing number

| Obligation | Covered | Penalty stated | Status / source |
|---|---|---|---|
| WP registration before advertising or renting; expires Sept 30 | Yes: WP `str_registration` (fixed 09-30) | Ord. 574: warning / $500 / $1,000 and/or revocation + ban up to 2 yrs; each day a separate offense | Confirmed: https://wpgov.com/good-neighbor/; https://wpgov.com/wp-content/uploads/2022/05/O574.pdf |
| WP registration number in every ad, worded "Winter Park Short-Term Rental Registration No. [#]" | Partially: `listing_match` checks the number is present, not the wording | Same ladder | Confirmed: Ord. 552 §3-10-5(A)(1) (https://wpgov.com/wp-content/uploads/2021/06/O552.pdf) |
| Fraser registration + permit number on listing | Yes: Fraser `str_registration` with `listing_match` | 1st warning (10 business days to cure); 2nd $500; 3rd $1,000; 4th revocation/suspension 1 yr | Confirmed: Fraser page; Ord. 488 (p); Ord. 516 (q) |
| Grand County permit; active permit number on every listing | Yes: GC `str_permit` with `listing_match` | §14.7(14): warning / $500 / $1,000 / revocation or suspension 1 yr on 4th within 2 yrs; cure in 10 days doesn't erase violation | Confirmed: https://www.co.grand.co.us/DocumentCenter/View/27506/Zoning-Regulations (§14.7) |
| Permit not transferable on sale (WP, Fraser) | No | — | Confirmed: Ord. 552 §3-10-4(B); Ord. 488 (g) |
| Caps on number of STR permits | No (none found) | — | Not found on any page opened for the three jurisdictions. `unverified` that none exist (WP town code at amlegal returned 403; Fraser municode not extractable). |
| WP high-impact STR (20+ occupants) needs special use permit first | No | Same ladder / SUP revocation | Confirmed: Ord. 552 §3-10-3(A), §3-10-4(C) |

### Occupancy, parking, septic

| Obligation | Covered | Penalty | Status / source |
|---|---|---|---|
| Grand County max occupancy 16 | Yes: `max_occupancy: 16`, `occupancy_check` | §14.7 ladder | Confirmed: https://www.co.grand.co.us/943/Short-Term-Rentals; §14.7(7)(b) |
| **Grand County OWTS (septic) cap: design volume + 2** | **No** | §14.7 ladder; OWTS failure is a renewal-denial ground (§14.7(4)) | Confirmed: §14.7(7)(b); FAQ https://www.co.grand.co.us/FAQ.aspx?QID=166 restates as "2 people per bedroom plus 2". **Operator / legal review**: which figure governs for each septic home (permit design volume vs FAQ shorthand). |
| **Fraser occupancy 2 per bedroom + 4 (studio 4)** | **No** formula; only a permit row's `permitted_occupancy` | Ord. 488 ladder | Confirmed: Ord. 488 §6-8-30(m) |
| WP occupancy limit | n/a | — | No WP occupancy formula found on pages opened (`unverified` that none exists in code). |
| Parking plan (Fraser, GC) | Yes: `parking_plan` in both | Ladders; Fraser revocation ground (o)(2) | Confirmed: Ord. 488 (n); §14.7(7)(c) |
| **WP: number of on-site spaces (or "no parking / no on-street parking") in every ad**; vehicles on-site only | **No** | Ord. 574 ladder | Confirmed: Ord. 552 §3-10-5(A)(2) |
| No sleeping in vehicles/tents (WP, GC) | No | Ladders | Confirmed: Ord. 552 §3-10-5(A)(2); §14.7(11) |
| WP no overnight street parking Nov 1–May 1 | No (guest rule) | Not stated | Confirmed: https://wpgov.com/good-neighbor/ |

### Life safety

| Obligation | Covered | Penalty | Status / source |
|---|---|---|---|
| **Smoke + CO detectors + extinguishers operable at all times (WP)** | **No** | Ord. 574 ladder | Confirmed: Ord. 552 §3-10-5(B)(4) |
| **Smoke + CO detectors; extinguisher each floor; egress clear of snow (Fraser)** | **No** | Ord. 488 ladder | Confirmed: Ord. 488 §6-8-30(l); Fraser page |
| **Smoke alarms (IBC), extinguishers, CO alarm within 15 ft of each sleeping room (GC)** | Partially: `safety_checklist` exists as one document; items not tracked | §14.7 ladder | Confirmed: §14.7(7)(e); checklist https://www.co.grand.co.us/FormCenter/Short-Term-Rentals-16/STR-Safety-Checklist-97 (5 lb extinguisher all floors, interconnected smoke alarms in bedrooms, CO near sleeping areas and gas appliances, egress) |
| Colorado CO alarm statute (C.R.S. 38-45-104, rental properties) | No | Not stated in act | Confirmed **as enacted in 2009**: HB09-1091 session law https://content.leg.colorado.gov/sites/default/files/images/olls/2009a_sl_51.pdf (CO alarm within 15 ft of each sleeping room in rentals with fuel-fired appliances or attached garage, on "change in tenant occupancy"; owner must replace missing/non-working alarms before a new occupancy). The current statute text was not opened. **Operator / legal review**: whether each STR stay is a "change in tenant occupancy" (it would mean a check at every turn). |
| East Grand Fire & Life Safety inspection (within 12 months at registration/renewal) | Yes WP, Fraser; GC marked **optional** | Registration refused without it | Confirmed: Ord. 624 (https://wpgov.com/wp-content/uploads/2025/01/O624.pdf); Ord. 516; https://eastgrandfire.com/fireprevention/str/ (covers unincorporated GC in district) |
| WP annual fireplace/stove cleaning | Yes: `fireplace_cleaning` (optional) | Ladder | Confirmed: Ord. 552 §3-10-5(B)(5) |
| Address visible from road (Fraser, GC) | No | Ladders | Confirmed: Ord. 488 (k); §14.7(7)(f) |
| Hot tub rules | No | — | `unverified`: no hot tub rule on any jurisdiction page opened; CDPHE pools page (https://cdphe.colorado.gov/swimming-pools-and-spas) **returned 403**. **Operator / legal review**: whether state spa rules reach a private-home STR hot tub. |

### Posting, contacts, trash, noise

| Obligation | Covered | Penalty | Status / source |
|---|---|---|---|
| WP: post registration + conditions in unit; post burn/drought restrictions | Partially: `posted_restrictions` (burn only) | Ladder | Confirmed: Ord. 552 §3-10-5(A)(7), (E)(1) |
| Fraser: post registration; post contact info | Partially: `posted_registration` only | Ladder | Confirmed: Ord. 488 (h), (i) |
| GC: post permit, both contacts, max occupancy statement, parking plan, garbage info, quiet times; give renter a permit copy | No | Ladder | Confirmed: §14.7(8) |
| Responsible agent / contacts: WP 60 min; Fraser 1.5 h; GC 2 residents, 1 h | Yes, existence only (`responsible_agent`, `emergency_contact`) | Ladders; Fraser revocation ground | Confirmed: Ord. 552 §3-10-5(A)(8); Ord. 488 (a)(3); §14.7(7)(a). Response-time performance is not tracked (an ops metric, not a document). |
| Contact-change notice: WP ≥ 7 days before; Fraser ≤ 7 days after; GC ≤ 5 business days | No | Ladders | Confirmed: same sources |
| Bear-proof / wildlife trash | GC yes (`bear_proof_trash`); Fraser **no**; WP no (Title 4 Ch. 10 not read) | **Fraser: $100 / $200 / misdemeanor** | Confirmed: Fraser page; §14.7(7)(d) |
| Quiet hours: WP 10 p.m.–8 a.m.; GC 7 p.m.–7 a.m. | No (guest-guide item) | GC complaints count against renewal | Confirmed: good-neighbor page; §14.7(10), (4) |

### Insurance

| Obligation | Covered | Penalty | Status / source |
|---|---|---|---|
| GC: owner "shall maintain appropriate liability insurance" (no minimum) | Yes: GC `liability_insurance` | Ladder | Confirmed: §14.7(13); county STR page lists "Liability insurance proof" |
| WP / Fraser insurance | Tracked (`liability_insurance`) but **no source requirement found** | — | Not found on any WP or Fraser page/ordinance opened. |
| Colorado statewide STR insurance minimum or platform obligation | No | — | `unverified`. A leg.colorado.gov-restricted search found no such bill. The $1M figure in commercial search snippets is a Denver city rule, not state law, and is out of scope. **Operator / legal review.** |

## Sources (all opened 2026-10-06)

| URL | Result |
|---|---|
| https://wpgov.com/good-neighbor/ | loaded |
| https://wpgov.com/doing-business/rent-your-home/ | loaded |
| https://wpgov.com/our-government/departments/finance/ | loaded |
| https://wpgov.com/our-government/departments/finance/sales-tax/ | loaded |
| https://wpgov.com/wp-content/uploads/2021/06/O552.pdf | loaded |
| https://wpgov.com/wp-content/uploads/2022/05/O574.pdf | loaded |
| https://wpgov.com/wp-content/uploads/2025/01/O624.pdf | loaded |
| https://wpgov.com/wp-content/uploads/2021/09/Short-Term-Rental-Information-Sheet.pdf | loaded |
| https://codelibrary.amlegal.com/codes/winterparkco/latest/winterpark_co/0-0-0-1873 | failed (403) |
| https://eastgrandfire.com/fireprevention/str/ | loaded |
| https://eastgrandfire.com/fireprevention/str/fire-life-safety-inspection/ | loaded |
| https://www.frasercolorado.com/303/Short-Term-Rental | loaded |
| https://frasercolorado.com/DocumentCenter/View/1577/Ordinance-No-488-Short-Term-Registration-Fees | loaded (read locally) |
| https://www.frasercolorado.com/DocumentCenter/View/2124/Ordinance-516-Amending-Chapter-6-Article-8-Short-Term-Rental-Registration | loaded |
| https://www.frasercolorado.com/DocumentCenter/View/401/Ordinance-NO-449--Short-Term-Rentals | loaded, not extractable |
| https://www.frasercolorado.com/DocumentCenter/View/709/Colorado-Tax-Info-STR-DR-1917 | failed (size limit) |
| https://library.municode.com/co/fraser/codes/municipal_code | not extractable |
| https://www.co.grand.co.us/943/Short-Term-Rentals | loaded |
| https://www.co.grand.co.us/DocumentCenter/View/17041/SECTION-148 | loaded (2021, superseded) |
| https://www.co.grand.co.us/DocumentCenter/View/27506/Zoning-Regulations | loaded (last amended 2026-07-28) |
| https://www.co.grand.co.us/FormCenter/Short-Term-Rentals-16/STR-Safety-Checklist-97 | loaded |
| https://www.co.grand.co.us/FAQ.aspx?QID=166 | loaded |
| https://www.co.grand.co.us/1470/Sales-Lodging-Tax | loaded |
| https://content.leg.colorado.gov/sites/default/files/images/olls/2009a_sl_51.pdf | loaded (HB09-1091 as enacted) |
| https://tax.colorado.gov/short-term-rentals | failed (403) |
| https://tax.colorado.gov/sites/tax/files/Sales%2011.pdf | failed (403) |
| https://tax.colorado.gov/sales-tax-guide | failed (403) |
| https://cdphe.colorado.gov/swimming-pools-and-spas | failed (403) |
