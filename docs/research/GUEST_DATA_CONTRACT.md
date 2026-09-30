# Guest data contract

Date: 2026-09-29

This is the only guest information the pricing database may store. It is taken from dossier 2. A field that is not in this table is out of scope, including name, email, phone, street address, message text, and payment data.

Colorado Privacy Act overview: https://coag.gov/resources/colorado-privacy-act/ (access 2026-09-29). City and party size can still be personal data if they can be linked back to a person. The minimization below is the control: no direct identifiers, and no raw Guesty guest object in `raw_json`.

## Fields

| Field | Source API | Channel availability | Privacy class | Retention | Use |
|---|---|---|---|---|---|
| `guest_city` | Guesty guest `hometown` (string or `{city}`) and the guest-report parameter `guestHometown`. https://open-api-docs.guesty.com/docs/fields-for-guest-reports | Channel-dependent. Airbnb often withholds hometown until booking. **Unknown** on `airbnb2` versus `website` until a dry-run sync counts non-null rows with values redacted. | Coarse location. Not a direct identifier by itself. | Same life as the reservation row, because pacing and ceiling history need the stay. | Segment context and, only when `models.demand_shifts_price` is on, a shadow input. Never a price by itself. |
| `guest_state` | Guest `address.state` or `guest.state` / `region` when Guesty sends it. | Same as city. Often missing on channel reservations. | Coarse location. | Same as the reservation row. | Origin mix. Not stored if only a street address was present. |
| `guest_country` | Guest `country` or `nationality`. https://open-api-docs.guesty.com/docs/create-a-reservation shows nationality next to email and phone; those contact fields are dropped. | Channel-dependent. | Coarse location. | Same as the reservation row. | International versus domestic mix. |
| `adults` | `numberOfGuests.numberOfAdults`. https://open-api-docs.guesty.com/reference/reservationsopenapicontroller_getreservationsbyids | Usually present on confirmed stays. **Unknown** on inquiries. | Party composition. | Same as the reservation row. | Party-size features. Combined with children and infants into `guest_count` when that integer is absent. |
| `children` | `numberOfGuests.numberOfChildren` | Same as adults. | Party composition. | Same as the reservation row. | Party-size features. |
| `infants` | `numberOfGuests.numberOfInfants` | Same as adults. | Party composition. | Same as the reservation row. | Party-size features. |
| `pets` | `numberOfGuests.numberOfPets` | Often missing. | Party composition. | Same as the reservation row. | Not a price input until a later flag says so. |

`guest_count` already exists. It stays the total headcount. It is not a new personal field.

## Explicitly excluded

| Data | Why it stays out |
|---|---|
| Full name, email, phone | Direct identifiers. The create-reservation example includes them. The sync drops them. |
| Street address | Not needed for a rate. A city is the finest grain this contract allows. |
| Guest messages and Airbnb host-insight screens | Host-login products. Do not scrape them. |
| Payment and payout fields | Already excluded. Fare accommodation is a rate fact, not a guest fact. |
| Pseudonymous repeat-guest hash | Open operator question. Not stored until the operator says yes. |
| Raw guest JSON | `raw_json` stays the minimized status, source, and timestamp blob. |

## Channel and sync rules

- Write the seven columns only from the Guesty reservation payload the sync already receives. No new guest endpoint and no purchased list.
- Null is the honest value when the channel omits the field. Do not backfill from a later message.
- Inquiries may carry party size and still must not block nights.
- A dry-run sync may log how many rows have a non-null city. It may not log the city.

## What this does not authorize

Buying a guest file, storing a marketing email, or turning any of these columns into an active pricing signal. Shadow signals from dossier 3 are separate and start at `shadow`.
