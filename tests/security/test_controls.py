"""Adversarial tests: unknown listing, wrong environment, missing secret, kill switch."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from src.db import DB_KIND_PRODUCTION, mark_db_identity
from src.pms import GuestyAdapter, PushResult, push_recommendations
from src.pms import guesty as guesty_mod
from src.security import kill_switch
from src.security.audit import REDACTED, record_event, redact
from src.security.environment import (
    CredentialPurpose, Environment, EnvironmentMismatch, MissingSecret,
    check_db_matches_environment, resolve_credential,
)
from src.security.scope import OutOfScope, PortfolioScope, ScopeError
from tests.security.conftest import PROPS, write_permit


# -- scope ---------------------------------------------------------------------

def test_scope_must_be_exactly_the_three_homes():
    with pytest.raises(ScopeError):
        PortfolioScope(PROPS | {"creekside_haven"})
    with pytest.raises(ScopeError):
        PortfolioScope(frozenset({"summit_haus"}))
    with pytest.raises(ScopeError):
        PortfolioScope(PROPS, {"LST-X": "creekside_haven"})


@pytest.mark.parametrize("boundary", ["sync", "webhook", "recommendation", "audit", "push"])
def test_unknown_listing_quarantines_and_audits_at_every_boundary(conn, scope, boundary):
    with pytest.raises(OutOfScope):
        scope.enforce(conn, boundary=boundary, listing_id="LST-UNKNOWN-9999")
    with pytest.raises(OutOfScope):
        scope.enforce(conn, boundary=boundary, property_id="creekside_haven")
    rows = conn.execute("SELECT boundary, detail_json FROM audit_events "
                        "WHERE event_type='scope_quarantine'").fetchall()
    assert [r["boundary"] for r in rows] == [boundary, boundary]
    # The full listing id never reaches the audit table (public repo, confidential ids).
    assert "LST-UNKNOWN-9999" not in rows[0]["detail_json"]
    assert scope.enforce(conn, boundary=boundary, listing_id="LST-C") == "cloud_9"


# -- environment and credentials --------------------------------------------------

def test_environment_and_db_identity_must_agree(conn, monkeypatch):
    monkeypatch.delenv("WP_PRICE_ENV", raising=False)
    with pytest.raises(EnvironmentMismatch):
        check_db_matches_environment(conn)
    monkeypatch.setenv("WP_PRICE_ENV", "production")
    with pytest.raises(EnvironmentMismatch):
        check_db_matches_environment(conn)          # db is 'unknown'
    mark_db_identity(conn, DB_KIND_PRODUCTION, "test")
    check_db_matches_environment(conn)
    for env in (Environment.STAGING, Environment.SIMULATION, Environment.DEMO):
        with pytest.raises(EnvironmentMismatch):
            check_db_matches_environment(conn, env)  # non-prod may never open prod


def test_write_credential_never_falls_back_to_read(monkeypatch):
    monkeypatch.setenv("GUESTY_CLIENT_ID", "read-id")
    monkeypatch.setenv("GUESTY_CLIENT_SECRET", "read-secret")
    monkeypatch.delenv("GUESTY_WRITE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GUESTY_WRITE_CLIENT_SECRET", raising=False)
    assert resolve_credential(CredentialPurpose.READ).client_id == "read-id"
    with pytest.raises(MissingSecret):
        resolve_credential(CredentialPurpose.WRITE)
    monkeypatch.setenv("GUESTY_WRITE_CLIENT_ID", "read-id")
    monkeypatch.setenv("GUESTY_WRITE_CLIENT_SECRET", "x")
    with pytest.raises(MissingSecret, match="distinct"):
        resolve_credential(CredentialPurpose.WRITE)
    monkeypatch.setenv("GUESTY_WRITE_CLIENT_ID", "write-id")
    cred = resolve_credential(CredentialPurpose.WRITE)
    assert "x" not in repr(cred) and "write-id" not in repr(cred)


# -- kill switch ----------------------------------------------------------------

def test_kill_switch_blocks_by_default(control):
    assert kill_switch.state("summit_haus").writes_allowed is False


@pytest.mark.parametrize("env, permit, reason", [
    ("staging", {}, "not production"),
    ("production", None, "no write permit"),
    ("production", {"writes_enabled": False}, "does not enable"),
    ("production", {"environment": "staging"}, "not for production"),
    ("production", {"approved_by": ""}, "approved_by"),
    ("production", {"expires_at": "2020-01-01T00:00:00+00:00"}, "expired"),
    ("production", {"expires_at": "2099-01-01T00:00:00"}, "timezone"),
    ("production", {"property_ids": ["cloud_9"]}, "does not cover"),
])
def test_kill_switch_fails_closed(control, monkeypatch, env, permit, reason):
    monkeypatch.setenv("WP_PRICE_ENV", env)
    if permit is not None:
        write_permit(control, **permit)
    st = kill_switch.state("summit_haus")
    assert st.writes_allowed is False and reason in st.reason


def test_kill_switch_malformed_permit_blocks(control, monkeypatch):
    monkeypatch.setenv("WP_PRICE_ENV", "production")
    (control / "write_permit.json").write_text("{not json")
    assert kill_switch.state("summit_haus").reason == "write permit unreadable"


def test_engaged_kill_switch_overrides_a_valid_permit(control, monkeypatch):
    monkeypatch.setenv("WP_PRICE_ENV", "production")
    write_permit(control)
    assert kill_switch.state("summit_haus").writes_allowed is True
    kill_switch.engage("test")
    st = kill_switch.state("summit_haus")
    assert st.writes_allowed is False and st.reason == "kill switch engaged"
    with pytest.raises(kill_switch.WriteBlocked):
        kill_switch.assert_write_permitted("summit_haus")


def test_set_rate_never_reaches_http_when_blocked(control, monkeypatch):
    """Final adapter boundary: wrong env / unknown listing / missing secret / kill → no PUT."""
    puts = []
    monkeypatch.setattr("requests.put", lambda *a, **k: puts.append(a))
    monkeypatch.setitem(guesty_mod.LOCKED_LISTING_PROPERTY_IDS, "LST-A", "summit_haus")
    client = guesty_mod.GuestyClient(client_id="w", client_secret="s", use_token_cache=False)
    client._token, client._expires_at = "tok", 1e12

    # wrong environment
    ok, err = client.set_rate("LST-A", date(2026, 12, 1), 900.0)
    assert not ok and "write blocked" in str(err)
    # unknown listing
    ok, err = client.set_rate("LST-UNKNOWN", date(2026, 12, 1), 900.0)
    assert "not in portfolio scope" in str(err)
    # missing write secret, even with env + permit
    monkeypatch.setenv("WP_PRICE_ENV", "production")
    write_permit(control)
    monkeypatch.delenv("GUESTY_WRITE_CLIENT_ID", raising=False)
    ok, err = client.set_rate("LST-A", date(2026, 12, 1), 900.0)
    assert "write credential missing" in str(err)
    # read credential in use
    monkeypatch.setenv("GUESTY_WRITE_CLIENT_ID", "other")
    monkeypatch.setenv("GUESTY_WRITE_CLIENT_SECRET", "s2")
    ok, err = client.set_rate("LST-A", date(2026, 12, 1), 900.0)
    assert "not using the write credential" in str(err)
    # kill switch engaged with everything else valid
    monkeypatch.setenv("GUESTY_WRITE_CLIENT_ID", "w")
    kill_switch.engage("drill")
    ok, err = client.set_rate("LST-A", date(2026, 12, 1), 900.0)
    assert "kill switch engaged" in str(err)
    assert puts == []


class _LiveFake:
    """Pretends to be a live adapter; records attempts instead of calling a vendor."""
    name = "live_fake"
    live = True

    def __init__(self):
        self.calls = []

    def fetch_calendar(self, *a, **k):
        return []

    def push_rate(self, property_id, stay_date, price, min_stay=None):
        self.calls.append((property_id, stay_date, price))
        return PushResult(property_id, stay_date, None, price, True, "applied")


class _Rec:
    def __init__(self, pid):
        self.property_id, self.stay_date = pid, date(2026, 12, 1)
        self.recommended_price, self.floor_price, self.listed_price_at_run = 900.0, 500.0, 880.0
        self.status, self.autonomy_level, self.run_id = "suggested", "handle", "r"
        self.rule_version = self.model_version = self.inputs_hash = "x"


def test_push_refuses_out_of_scope_and_kill_switched_writes(conn, control, monkeypatch):
    monkeypatch.setattr("src.security.scope.load_scope",
                        lambda c=None: PortfolioScope(PROPS, {}))
    adapter = _LiveFake()
    counts = push_recommendations(conn, [_Rec("creekside_haven"), _Rec("summit_haus")],
                                  adapter, "handle", policy={"guardrails": {}})
    assert adapter.calls == []
    assert counts["refused_scope"] == 1 and counts["refused_kill_switch"] == 1
    types = [r["event_type"] for r in conn.execute("SELECT event_type FROM audit_events")]
    assert sorted(types) == ["scope_quarantine", "write_refused"]


def test_guesty_adapter_is_marked_live():
    assert GuestyAdapter.live is True


# -- redaction --------------------------------------------------------------------

def test_redaction_removes_secrets_and_guest_identity(conn):
    detail = {"client_secret": "abc", "guest": {"email": "a@b.co", "fullName": "X Y"},
              "note": "Bearer abcdefghijklmnop call +1 (970) 555-1212 a@b.co",
              "nested": [{"token": "t"}], "price": 900}
    clean = redact(detail)
    blob = json.dumps(clean)
    for leaked in ("abc\"", "a@b.co", "X Y", "abcdefghijklmnop", "555-1212"):
        assert leaked not in blob
    assert clean["price"] == 900 and clean["client_secret"] == REDACTED
    record_event(conn, event_type="credential", boundary="audit", detail=detail)
    assert "a@b.co" not in conn.execute("SELECT detail_json FROM audit_events").fetchone()[0]


def test_permit_check_never_raises(control, monkeypatch):
    monkeypatch.setenv("WP_PRICE_ENV", "production")
    (control / "write_permit.json").mkdir()   # unreadable as a file
    assert kill_switch.state("summit_haus").writes_allowed is False


def test_kill_switch_cli_engage_and_status(control, capsys):
    assert kill_switch.main(["engage", "--reason", "drill"]) == 0
    kill_switch.main(["status"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["writes_allowed"] is False and out["reason"] == "kill switch engaged"


def test_permit_expiry_is_evaluated_at_call_time(control, monkeypatch):
    monkeypatch.setenv("WP_PRICE_ENV", "production")
    write_permit(control)
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    assert kill_switch.state("summit_haus", now=later).reason == "write permit expired"
