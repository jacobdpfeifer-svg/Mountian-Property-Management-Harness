"""Local run receipts, autonomy ceilings, incidents, alerts, and backup/restore.

Everything here writes local files only. A production alert destination,
log/metric store, and encrypted off-host backup are not built; `AlertSink` is
the seam where they attach (BLOCKED on operator-chosen services).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from src.security.audit import redact

AUTONOMY_ORDER = ("observe", "suggest", "handle")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- source health -> autonomy ------------------------------------------------------

@dataclass(frozen=True)
class SourceHealth:
    source: str
    state: str                 # fresh | stale | missing | malformed | partial
    required: bool = True
    detail: str = ""


@dataclass(frozen=True)
class AutonomyDecision:
    ceiling: str
    reasons: tuple[str, ...]


def autonomy_ceiling(health: list[SourceHealth], *, reconciliation_exceptions: int = 0,
                     readback_mismatches: int = 0, requested: str = "handle") -> AutonomyDecision:
    """The most authority the evidence allows. Degraded inputs only ever lower it."""
    ceiling = AUTONOMY_ORDER.index(requested)
    reasons = []
    for h in health:
        if h.state == "fresh":
            continue
        if h.required and h.state in ("stale", "missing", "malformed"):
            ceiling = min(ceiling, AUTONOMY_ORDER.index("observe"))
        else:
            ceiling = min(ceiling, AUTONOMY_ORDER.index("suggest"))
        reasons.append(f"{h.source}:{h.state}")
    if reconciliation_exceptions:
        ceiling = min(ceiling, AUTONOMY_ORDER.index("suggest"))
        reasons.append(f"reconciliation_exceptions:{reconciliation_exceptions}")
    if readback_mismatches:
        ceiling = AUTONOMY_ORDER.index("observe")
        reasons.append(f"readback_mismatches:{readback_mismatches}")
    return AutonomyDecision(AUTONOMY_ORDER[ceiling], tuple(reasons))


# -- receipts -------------------------------------------------------------------------

@dataclass
class RunReceipt:
    job: str
    run_date: str
    status: str                          # ok | degraded | failed | skipped | missed
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None
    attempts: int = 0
    autonomy_ceiling: str | None = None
    source_health: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    code_sha: str | None = None


def write_receipt(root: Path, receipt: RunReceipt) -> Path:
    """Append-only: one file per (run_date, job, run_id); never overwritten."""
    receipt.finished_at = receipt.finished_at or _now()
    path = root / "receipts" / receipt.run_date / f"{receipt.job}.{receipt.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:
        json.dump(redact(asdict(receipt)), fh, indent=1, sort_keys=True)
    return path


def receipts_for(root: Path, run_date: str, job: str | None = None) -> list[dict[str, Any]]:
    d = root / "receipts" / run_date
    if not d.exists():
        return []
    pattern = f"{job}.*.json" if job else "*.json"
    return [json.loads(p.read_text()) for p in sorted(d.glob(pattern))]


# -- incidents and alerts ---------------------------------------------------------------

class AlertSink(Protocol):
    def send(self, alert: dict[str, Any]) -> None: ...


class LocalAlertSink:
    """Writes alerts to a local JSONL file. Stand-in for paging/email (BLOCKED)."""

    def __init__(self, root: Path):
        self.path = root / "alerts.jsonl"

    def send(self, alert: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(redact(alert), sort_keys=True) + "\n")


SEVERITIES = ("sev1", "sev2", "sev3")


def open_incident(root: Path, *, severity: str, kind: str, summary: str,
                  evidence: dict[str, Any], sink: AlertSink | None = None) -> Path:
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}")
    incident = {"incident_id": f"INC-{uuid.uuid4().hex[:10]}", "opened_at": _now(),
                "severity": severity, "kind": kind, "summary": summary,
                "evidence": redact(evidence), "autonomy_action": "lowered to observe"
                if severity in ("sev1", "sev2") else "unchanged"}
    path = root / "incidents" / f"{incident['incident_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(incident, indent=1, sort_keys=True), encoding="utf-8")
    (sink or LocalAlertSink(root)).send({"type": "incident", **incident})
    return path


# -- backup / restore -----------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_db(source: Path, dest_dir: Path) -> Path:
    """Consistent online copy (SQLite backup API) plus a checksum manifest.

    Local and unencrypted: encryption at rest and off-host retention are BLOCKED
    on an operator-chosen storage/KMS service.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = dest_dir / f"{source.stem}.{stamp}.{uuid.uuid4().hex[:6]}.db"
    src = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
    dst = sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    manifest = {"source": source.name, "backup": out.name, "sha256": _sha256(out),
                "bytes": out.stat().st_size, "created_at": _now()}
    out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return out


class RestoreError(RuntimeError):
    pass


def restore_db(backup: Path, target: Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Verify checksum and integrity, then restore atomically. Never silently clobbers."""
    manifest_path = backup.with_suffix(".manifest.json")
    if not manifest_path.exists():
        raise RestoreError("backup manifest missing")
    manifest = json.loads(manifest_path.read_text())
    if _sha256(backup) != manifest["sha256"]:
        raise RestoreError("backup checksum mismatch")
    conn = sqlite3.connect(f"{backup.resolve().as_uri()}?mode=ro", uri=True)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if result != "ok":
        raise RestoreError(f"integrity check failed: {result}")
    if target.exists() and not overwrite:
        raise RestoreError(f"refusing to overwrite {target.name} without overwrite=True")
    tmp = target.with_suffix(".restore-tmp")
    shutil.copyfile(backup, tmp)
    os.replace(tmp, target)
    return {"restored": target.name, "sha256": manifest["sha256"], "integrity": result}
