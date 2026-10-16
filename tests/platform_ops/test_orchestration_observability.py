"""Chaos tests for orchestration plus observability/backup proofs (06E, 06F)."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import date
from pathlib import Path

import pytest

from src.observability import (
    RestoreError, RunReceipt, SourceHealth, autonomy_ceiling, backup_db, open_incident,
    restore_db, write_receipt,
)
from src.orchestration import JobOutcome, Orchestrator, RunLocked, daily_jobs

DAY = date(2026, 12, 10)


def _ok(_d):
    return JobOutcome("ok")


def _fns(**over):
    fns = {n: _ok for n in ("snapshot", "pms_sync", "comp_collection", "signals", "ops_import",
                            "recommendation", "review_artifact", "outcome_reconciliation")}
    fns.update(over)
    return fns


def _orch(tmp_path, overrides=None, **over):
    return Orchestrator(tmp_path, daily_jobs(_fns(**over), **(overrides or {})), sleep=lambda s: None)


def _seed_history(root: Path, days=7):
    for back in range(1, days + 1):
        write_receipt(root, RunReceipt(job="snapshot", run_date=date.fromordinal(DAY.toordinal() - back).isoformat(),
                                       status="ok"))


def test_clean_run_grants_handle(tmp_path):
    _seed_history(tmp_path)
    r = _orch(tmp_path).run(DAY)
    assert r.autonomy == "handle" and r.missed_snapshots == [] and r.incidents == []


def test_missed_snapshot_is_reported_and_never_backfilled(tmp_path):
    _seed_history(tmp_path)
    gap = "2026-12-07"
    for p in (tmp_path / "receipts" / gap).glob("*.json"):
        p.unlink()
    r = _orch(tmp_path).run(DAY)
    assert r.missed_snapshots == [gap]
    assert not list((tmp_path / "receipts" / gap).glob("*.json"))  # still missing
    assert r.autonomy == "suggest"


def test_slow_source_hits_deadline_and_blocks_downstream(tmp_path):
    _seed_history(tmp_path)

    def slow(_d):
        time.sleep(0.5)
        return JobOutcome("ok")

    r = _orch(tmp_path, {"pms_sync": {"deadline_s": 0.05}}, pms_sync=slow).run(DAY)
    assert r.receipts["pms_sync"]["status"] == "failed"
    assert "deadline" in r.receipts["pms_sync"]["errors"][0]
    assert r.receipts["pms_sync"]["attempts"] == 1
    assert r.receipts["recommendation"]["status"] == "skipped"
    assert r.receipts["review_artifact"]["status"] == "skipped"
    assert r.autonomy == "observe" and r.incidents


def test_partial_ingest_degrades_authority(tmp_path):
    _seed_history(tmp_path)
    r = _orch(tmp_path, pms_sync=lambda d: JobOutcome("degraded", "2 of 3 listings")).run(DAY)
    assert r.receipts["recommendation"]["status"] == "ok"   # may run, on flagged input
    assert r.autonomy == "suggest"


def test_retry_with_backoff_then_success(tmp_path):
    _seed_history(tmp_path)
    calls = {"n": 0}
    sleeps = []

    def flaky(_d):
        calls["n"] += 1
        if calls["n"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return JobOutcome("ok")

    o = Orchestrator(tmp_path, daily_jobs(_fns(signals=flaky)), sleep=sleeps.append)
    r = o.run(DAY)
    assert r.receipts["signals"]["status"] == "ok" and r.receipts["signals"]["attempts"] == 3
    assert sleeps == [5.0, 10.0]


def test_persistent_db_lock_fails_with_receipt(tmp_path):
    _seed_history(tmp_path)

    def locked(_d):
        raise sqlite3.OperationalError("database is locked")

    r = _orch(tmp_path, snapshot=locked).run(DAY)
    assert r.receipts["snapshot"]["status"] == "failed"
    assert r.receipts["snapshot"]["attempts"] == 3
    assert r.autonomy == "observe"


def test_repeat_run_is_idempotent(tmp_path):
    _seed_history(tmp_path)
    calls = {"n": 0}

    def counted(_d):
        calls["n"] += 1
        return JobOutcome("ok")

    o = _orch(tmp_path, recommendation=counted)
    o.run(DAY)
    o.run(DAY)
    assert calls["n"] == 1


def test_concurrent_run_is_refused(tmp_path):
    import os
    (tmp_path / "orchestrator.lock").write_text(json.dumps({"pid": os.getpid()}))
    with pytest.raises(RunLocked, match="holds the lock"):
        _orch(tmp_path).run(DAY)
    (tmp_path / "orchestrator.lock").write_text(json.dumps({"pid": 999999}))
    with pytest.raises(RunLocked, match="stale lock"):
        _orch(tmp_path).run(DAY)


def test_dag_rejects_cycles_and_unknown_deps(tmp_path):
    from src.orchestration import JobSpec
    with pytest.raises(ValueError):
        Orchestrator(tmp_path, [JobSpec("a", _ok, ("b",)), JobSpec("b", _ok, ("a",))])
    with pytest.raises(ValueError):
        Orchestrator(tmp_path, [JobSpec("a", _ok, ("zzz",))])
    with pytest.raises(ValueError):
        daily_jobs({"snapshot": _ok})


@pytest.mark.parametrize("health, extra, expected", [
    ([SourceHealth("pms", "fresh")], {}, "handle"),
    ([SourceHealth("pms", "stale")], {}, "observe"),
    ([SourceHealth("comps", "missing", required=False)], {}, "suggest"),
    ([SourceHealth("pms", "fresh")], {"reconciliation_exceptions": 2}, "suggest"),
    ([SourceHealth("pms", "fresh")], {"readback_mismatches": 1}, "observe"),
])
def test_autonomy_only_ever_lowers(health, extra, expected):
    assert autonomy_ceiling(health, **extra).ceiling == expected


def test_injected_failures_produce_alert_and_incident(tmp_path):
    path = open_incident(tmp_path, severity="sev1", kind="readback_mismatch",
                         summary="read-back mismatch", evidence={"token": "secret-value"})
    inc = json.loads(path.read_text())
    assert inc["autonomy_action"] == "lowered to observe"
    alerts = (tmp_path / "alerts.jsonl").read_text()
    assert "readback_mismatch" in alerts and "secret-value" not in alerts


def test_receipts_are_never_overwritten(tmp_path):
    r = RunReceipt(job="x", run_date="2026-12-10", status="ok")
    write_receipt(tmp_path, r)
    with pytest.raises(FileExistsError):
        write_receipt(tmp_path, r)


def test_backup_and_restore_exercise(tmp_path):
    db = tmp_path / "live.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE t (x)")
    c.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(100)])
    c.commit()
    c.close()
    backup = backup_db(db, tmp_path / "backups")
    target = tmp_path / "restored.db"
    out = restore_db(backup, target)
    assert out["integrity"] == "ok"
    assert sqlite3.connect(target).execute("SELECT COUNT(*) FROM t").fetchone()[0] == 100
    with pytest.raises(RestoreError, match="overwrite"):
        restore_db(backup, target)
    with open(backup, "r+b") as fh:
        fh.seek(200)
        fh.write(b"corrupt")
    with pytest.raises(RestoreError, match="checksum"):
        restore_db(backup, tmp_path / "other.db")
