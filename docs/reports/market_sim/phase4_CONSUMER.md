# Phase 4 — Consumer layer

Date: 2026-09-29
Branch: `feature/market-sim-and-learning`

## What was done

Guest storage is limited to the contract in `docs/research/GUEST_DATA_CONTRACT.md`: city, state, country, and party composition. Names, emails, phones, and street addresses are not columns and are not copied into `raw_json`.

Inquiry conversion reads Guesty inquiry rows in `reservations` when a property has at least five of them. A sample database with only the CSV `booking_inquiries` table still uses that table.

Five dossier-3 indicators are registered at `shadow` and are not promoted to `active`. `models.demand_shifts_price` is the only price path that reads one of them (`macro.consumer_confidence`), and only when that flag is on.

Segment shares stay in the scenario files transcribed in Phase 2. They were not edited to fit an engine score.

## Files changed

- `docs/research/GUEST_DATA_CONTRACT.md`
- `src/db/schema.sql` and `src/db/__init__.py` — `guest_city`, `guest_state`, `guest_country`, `adults`, `children`, `infants`, `pets` on `reservations`.
- `src/pms/guesty.py` — `extract_party`, `extract_guest_place`. Integer `guestsCount` still works. A `numberOfGuests` object is not cast with `int()`.
- `src/pms/sync.py` — writes the seven columns. `raw_json` stays status, source, timestamps, and guest count.
- `src/elasticity/__init__.py` — Guesty inquiry rows first, CSV second.
- `src/signals/consumer.py` — shadow registration.
- `tests/test_guest_fields.py`, `tests/test_guesty.py`, `tests/test_consumer_signals.py`.

## Tests

Passing:

```
.venv/bin/python -m pytest -q tests/test_guest_fields.py tests/test_consumer_signals.py \
  tests/test_guesty.py::test_sync_stores_city_and_party_and_drops_contact_fields \
  tests/test_guesty.py::test_inquiry_conversion_reads_guesty_inquiry_rows --tb=short
```

The contact-field test syncs a realistic reservation with `fullName`, `email`, `phone`, and a street address. The row stores Denver / CO / US and 6 adults, 2 children, 1 infant, 0 pets. The email, name, and phone are absent from `raw_json`.

The signal test registers all five keys at `shadow`, writes one observation before 2026-09-29 and one after, and `assert_no_lookahead` does not raise. The later row is not returned.

Full default suite after this phase and Phase 3: 417 passed, 2 deselected, exit 0.

## Commands

No Guesty call was made. Tests use an in-memory-shaped fake client and `init_db` on a temp file.

## Proven, suggestive, unknown

- **Proven.** The sync of the fixture reservation does not persist the email, phone, or name. Exit 0 on the test above.
- **Proven.** Five inquiry rows and two confirmed rows on `test_haus` convert at 2/5. Fewer than five inquiry rows still returns None from the Guesty path so the CSV table can answer.
- **Proven.** The five new definitions start at shadow. A future `observed_at` is not readable at an earlier `as_of`.
- **Unknown.** How often Airbnb actually sends hometown. The contract says to count non-null cities on a dry-run sync and not to log the city. That dry run was not executed against the live account in this phase.
- **Suggestive.** City and party size can still be personal data under the Colorado Privacy Act if they can be linked back to a person. The control is the minimization, not a claim that the columns are anonymous.

## Deviations

No purchased guest file. No repeat-guest hash. The pseudonymous hash stays an open question and is not stored.

`load_resort_config()` still reads `config/resort/winter_park.yaml` only. Telluride is a separate file and is not seeded into the live resort reference.

## Open operator questions

Will you allow a dry-run sync that logs only the count of non-null cities, with the cities themselves redacted? The repeat-guest hash is still unanswered and is not in the database.
