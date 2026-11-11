"""The canary packet reports blockers. It does not create an authorization."""

from src.db import connect, init_db
from src.db.migrations import apply_migrations
from src.experiments.readiness import PACKET_BLOCKED, canary_signoff_packet


def test_packet_lists_blockers_and_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("GUESTY_WRITE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GUESTY_WRITE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("WP_PRICE_ENV", raising=False)
    path = tmp_path / "r.db"
    init_db(path, seed_markets=False)
    conn = connect(path)
    apply_migrations(conn)
    packet = canary_signoff_packet(
        conn=conn, ledger=tmp_path / "missing.jsonl", register_path=tmp_path / "missing.register.json",
        plan_path=tmp_path / "missing.plan.json", signoff_path=tmp_path / "canary_signoff.json",
        permit_path=tmp_path / "write_permit.json", deployed_sha_path=tmp_path / "DEPLOYED_SHA",
        alert_destination=None, backup_destination=None)
    assert packet["status"] == PACKET_BLOCKED
    assert packet["authorization_created"] is False
    ids = {b["id"] for b in packet["blockers"]}
    assert {"write_credential", "signed_scope", "write_permit", "deployed_sha", "alerts", "backup",
            "field_plan", "evaluation", "shadow"} <= ids
    assert not (tmp_path / "canary_signoff.json").exists()
    assert not (tmp_path / "write_permit.json").exists()
    conn.close()
