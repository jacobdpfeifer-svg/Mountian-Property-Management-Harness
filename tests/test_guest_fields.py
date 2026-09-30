"""Minimized guest fields. Names, emails, and phones never leave this parser."""

from src.pms.guesty import extract_guest_place, extract_party, reservation_guest_count


def test_party_and_place_keep_only_the_contract_fields():
    raw = {
        "guest": {
            "fullName": "Should Not Store",
            "email": "nope@example.com",
            "phone": "555-0100",
            "hometown": "Denver",
            "address": {"street": "1 Main", "state": "CO", "country": "US"},
        },
        "numberOfGuests": {
            "numberOfAdults": 6,
            "numberOfChildren": 2,
            "numberOfInfants": 1,
            "numberOfPets": 0,
        },
    }
    place = extract_guest_place(raw)
    party = extract_party(raw)
    assert place == {"city": "Denver", "state": "CO", "country": "US"}
    assert "street" not in place.values()
    assert party == {"adults": 6, "children": 2, "infants": 1, "pets": 0}
    assert reservation_guest_count(raw) == 9
    blob = str(place) + str(party)
    assert "Should Not Store" not in blob
    assert "nope@example.com" not in blob
    assert "555-0100" not in blob


def test_guest_count_still_reads_a_plain_integer():
    assert reservation_guest_count({"guestsCount": 12}) == 12
    assert reservation_guest_count({}) is None
