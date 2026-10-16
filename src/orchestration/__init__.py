"""Dependency-aware daily orchestration with explicit degraded results.

`Orchestrator.run(run_date)` executes the declared daily DAG once per date:

- a file lock prevents two runs at once (a stale lock from a dead pid is reported,
  not silently stolen);
- a job that already finished ok/degraded for this date is not re-run
  (idempotent repeat), and its receipt is reused;
- each job has a deadline, bounded retries with backoff, and a receipt;
- a job whose required dependency failed is `skipped`, never run on partial input;
- a missed prior-day snapshot is reported as `missed` and never backfilled: a
  pacing observation that was not taken that day cannot be reconstructed;
- the run's autonomy ceiling is computed from what actually happened.

Job bodies are injected. Wiring them to the existing CLI commands is integration
work (src/cli/main.py is not edited here).
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from src.observability import (
    RunReceipt, SourceHealth, autonomy_ceiling, open_incident, receipts_for, write_receipt,
)


@dataclass(frozen=True)
class JobOutcome:
    status: str                      # ok | degraded | failed
    detail: str = ""
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class JobSpec:
    name: str
    fn: Callable[[date], JobOutcome]
    deps: tuple[str, ...] = ()
    deadline_s: float = 600.0
    retries: int = 2
    backoff_s: float = 5.0
    required: bool = True            # a failure here forces autonomy to observe
    owner: str = "operator"


# Declared daily jobs, their dependencies, and whether each is required for
# authority above `observe`. Owners/schedules/alerts are in docs/runbooks.
DAILY_DAG: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("snapshot", (), True),
    ("pms_sync", (), True),
    ("comp_collection", (), False),
    ("signals", (), False),
    ("ops_import", (), False),
    ("recommendation", ("snapshot", "pms_sync"), True),
    ("review_artifact", ("recommendation",), True),
    ("outcome_reconciliation", ("pms_sync",), False),
)


class RunLocked(RuntimeError):
    pass


@dataclass
class RunResult:
    run_date: str
    receipts: dict[str, dict]
    autonomy: str
    reasons: tuple[str, ...]
    missed_snapshots: list[str]
    incidents: list[str]


class Orchestrator:
    def __init__(self, root: Path, jobs: list[JobSpec], *, sleep: Callable[[float], None] = time.sleep,
                 snapshot_job: str = "snapshot", lookback_days: int = 7):
        names = [j.name for j in jobs]
        if len(set(names)) != len(names):
            raise ValueError("duplicate job names")
        for j in jobs:
            unknown = set(j.deps) - set(names)
            if unknown:
                raise ValueError(f"{j.name} depends on unknown jobs {sorted(unknown)}")
        self.root, self.jobs, self.sleep = root, self._toposort(jobs), sleep
        self.snapshot_job, self.lookback_days = snapshot_job, lookback_days

    @staticmethod
    def _toposort(jobs: list[JobSpec]) -> list[JobSpec]:
        done: list[JobSpec] = []
        pending = list(jobs)
        while pending:
            ready = [j for j in pending if all(d in {x.name for x in done} for d in j.deps)]
            if not ready:
                raise ValueError("dependency cycle")
            done.extend(ready)
            pending = [j for j in pending if j not in ready]
        return done

    # -- lock -----------------------------------------------------------------------
    def _acquire(self) -> Path:
        lock = self.root / "orchestrator.lock"
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                pid = int(json.loads(lock.read_text()).get("pid", -1))
                os.kill(pid, 0)
                alive = True
            except (ValueError, OSError, json.JSONDecodeError):
                alive = False
            raise RunLocked("another daily run holds the lock" if alive else
                            f"stale lock at {lock}; confirm no run is active, then remove it") from None
        with os.fdopen(fd, "w") as fh:
            json.dump({"pid": os.getpid(), "started": time.time()}, fh)
        return lock

    # -- one job ----------------------------------------------------------------------
    def _run_job(self, spec: JobSpec, run_date: date) -> RunReceipt:
        receipt = RunReceipt(job=spec.name, run_date=run_date.isoformat(), status="failed")
        for attempt in range(spec.retries + 1):
            receipt.attempts = attempt + 1
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                outcome = pool.submit(spec.fn, run_date).result(timeout=spec.deadline_s)
            except FutureTimeout:
                # Python cannot kill the thread; the job is recorded failed and
                # nothing downstream consumes its partial output.
                outcome = JobOutcome("failed", f"deadline {spec.deadline_s}s exceeded")
            except Exception as exc:
                outcome = JobOutcome("failed", f"{type(exc).__name__}: {str(exc)[:200]}")
            finally:
                pool.shutdown(wait=False)
            receipt.status, receipt.metrics = outcome.status, dict(outcome.metrics)
            if outcome.detail:
                receipt.errors.append(f"attempt {attempt + 1}: {outcome.detail}")
            if outcome.status != "failed" or "deadline" in outcome.detail:
                break  # a deadline overrun is not retried into the next deadline
            if attempt < spec.retries:
                self.sleep(spec.backoff_s * (2 ** attempt))
        return receipt

    # -- the run ----------------------------------------------------------------------
    def missed_snapshots(self, run_date: date) -> list[str]:
        missed = []
        for back in range(1, self.lookback_days + 1):
            d = (run_date - timedelta(days=back)).isoformat()
            done = [r for r in receipts_for(self.root, d, self.snapshot_job) if r["status"] in ("ok", "degraded")]
            if not done:
                missed.append(d)
        return missed

    def run(self, run_date: date) -> RunResult:
        lock = self._acquire()
        try:
            return self._run(run_date)
        finally:
            lock.unlink(missing_ok=True)

    def _run(self, run_date: date) -> RunResult:
        key = run_date.isoformat()
        results: dict[str, dict] = {}
        incidents: list[str] = []
        for spec in self.jobs:
            prior = [r for r in receipts_for(self.root, key, spec.name) if r["status"] in ("ok", "degraded")]
            if prior:
                results[spec.name] = prior[-1]        # idempotent repeat
                continue
            blocked = [d for d in spec.deps if results.get(d, {}).get("status") not in ("ok", "degraded")]
            if blocked:
                receipt = RunReceipt(job=spec.name, run_date=key, status="skipped",
                                     errors=[f"dependency not satisfied: {', '.join(blocked)}"])
            else:
                receipt = self._run_job(spec, run_date)
            write_receipt(self.root, receipt)
            results[spec.name] = json.loads(json.dumps(receipt.__dict__))
            if receipt.status == "failed" and spec.required:
                incidents.append(str(open_incident(
                    self.root, severity="sev2", kind="job_failed", summary=f"{spec.name} failed",
                    evidence={"job": spec.name, "run_date": key, "errors": receipt.errors})))
        missed = self.missed_snapshots(run_date)
        required = {j.name: j.required for j in self.jobs}
        health = []
        for name, r in results.items():
            state = {"ok": "fresh", "degraded": "partial", "failed": "missing", "skipped": "missing"}[r["status"]]
            health.append(SourceHealth(name, state, required[name]))
        if missed:
            health.append(SourceHealth("snapshot_history", "partial", False, f"missed {len(missed)} day(s)"))
        decision = autonomy_ceiling(health)
        return RunResult(key, results, decision.ceiling, decision.reasons, missed, incidents)


def daily_jobs(fns: dict[str, Callable[[date], JobOutcome]], **overrides: dict) -> list[JobSpec]:
    """Build the declared DAG from injected job bodies; every declared job must be provided."""
    missing = [name for name, _, _ in DAILY_DAG if name not in fns]
    if missing:
        raise ValueError(f"no implementation for declared jobs: {missing}")
    return [JobSpec(name, fns[name], deps, required=req, **overrides.get(name, {}))
            for name, deps, req in DAILY_DAG]
