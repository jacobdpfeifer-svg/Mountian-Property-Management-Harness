"""Preregistered experiment register, screen gate, and paired evidence (06G/06H).

Rules this module enforces:

- A register is frozen (written once, content-hashed) before any evaluation.
- Screen and evaluation seeds are disjoint; screen and evaluation scenario sets
  are declared up front.
- The candidate policy and calibration files are hashed at freeze time; opening
  evaluation refuses if either changed (no tuning after the freeze).
- Evaluation may be opened only after a recorded screen decision of
  `ADVANCE_TO_EVALUATION`. The screen gate is computed from screen seeds only.
- Opening is recorded once, append-only; a second opening is refused.

It runs no simulation. Evaluation runs remain serial market-sim jobs under the
global run lock (src/proving_ground/run_lock.py).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

DECISIONS = ("ADVANCE_TO_EVALUATION", "REWORK", "REJECT")


class RegisterError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def freeze_register(register: dict[str, Any], out: Path, *, repo: Path) -> dict[str, Any]:
    """Validate, hash inputs, and write the register once. Returns the frozen body."""
    required = ["experiment_id", "candidate_policy", "calibration", "objective", "comparator",
                "material_harm_margin", "screen", "evaluation", "metrics", "stop_conditions"]
    missing = [k for k in required if k not in register]
    if missing:
        raise RegisterError(f"register missing {missing}")
    s_seeds, e_seeds = set(register["screen"]["seeds"]), set(register["evaluation"]["seeds"])
    if s_seeds & e_seeds:
        raise RegisterError(f"screen and evaluation seeds overlap: {sorted(s_seeds & e_seeds)}")
    if not register["evaluation"]["scenarios"]:
        raise RegisterError("evaluation scenarios must be declared before freezing")
    if out.exists():
        raise RegisterError(f"{out.name} is already frozen; a change needs a new experiment_id")
    body = dict(register)
    body["input_sha256"] = {
        "candidate_policy": sha256_file(repo / register["candidate_policy"]),
        "calibration": sha256_file(repo / register["calibration"]),
    }
    body["frozen_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body["register_sha256"] = hashlib.sha256(_canonical({k: v for k, v in body.items()
                                                         if k != "frozen_at"})).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
    return body


def load_register(path: Path) -> dict[str, Any]:
    body = json.loads(path.read_text())
    check = hashlib.sha256(_canonical({k: v for k, v in body.items()
                                       if k not in ("frozen_at", "register_sha256")})).hexdigest()
    if check != body.get("register_sha256"):
        raise RegisterError("register content does not match its hash (edited after freeze)")
    return body


# -- statistics -----------------------------------------------------------------------

@dataclass(frozen=True)
class PairedInterval:
    n: int
    mean: float
    lo: float
    hi: float
    min: float
    max: float
    favourable: int


def paired_interval(deltas: Iterable[float], *, level: float = 0.95, draws: int = 10_000,
                    seed: int = 20261015) -> PairedInterval:
    """Percentile bootstrap of the mean paired delta (candidate − comparator)."""
    d = [float(x) for x in deltas]
    if len(d) < 2:
        raise ValueError("need at least two paired seeds")
    rng = random.Random(seed)
    boots = sorted(mean(rng.choice(d) for _ in d) for _ in range(draws))
    a = (1 - level) / 2
    return PairedInterval(len(d), round(mean(d), 2), round(boots[int(a * draws)], 2),
                          round(boots[int((1 - a) * draws) - 1], 2), round(min(d), 2), round(max(d), 2),
                          sum(1 for x in d if x > 0))


def screen_decision(deltas: Iterable[float], *, margin: float, reject_below: float | None = None
                    ) -> tuple[str, PairedInterval, str]:
    """Gate on screen seeds only.

    ADVANCE_TO_EVALUATION: the interval's lower bound is above −margin.
    REJECT: the interval's upper bound is below −reject_below (clear, large harm).
    REWORK: anything else.
    """
    ci = paired_interval(deltas)
    if ci.lo > -margin:
        return "ADVANCE_TO_EVALUATION", ci, f"lower bound {ci.lo:+,.0f} > −{margin:,.0f}"
    if reject_below is not None and ci.hi < -reject_below:
        return "REJECT", ci, f"upper bound {ci.hi:+,.0f} < −{reject_below:,.0f}"
    return "REWORK", ci, f"lower bound {ci.lo:+,.0f} ≤ −{margin:,.0f}; harm not excluded"


def failure_regions(rows: Iterable[dict[str, Any]], keys: tuple[str, ...], *, margin: float,
                    delta_field: str = "delta") -> list[dict[str, Any]]:
    """Segments whose mean paired delta is worse than −margin."""
    groups: dict[tuple, list[float]] = {}
    for r in rows:
        groups.setdefault(tuple(r[k] for k in keys), []).append(float(r[delta_field]))
    out = []
    for k, v in sorted(groups.items()):
        m = mean(v)
        if m < -margin:
            out.append({**dict(zip(keys, k)), "n": len(v), "mean_delta": round(m, 2)})
    return out


def reliability(probs: Iterable[float], outcomes: Iterable[int], *, bins: int = 10) -> dict[str, Any]:
    """Brier score, base-rate Brier, and a binned reliability table."""
    p, y = [float(x) for x in probs], [int(o) for o in outcomes]
    if len(p) != len(y) or not p:
        raise ValueError("probabilities and outcomes must be equal-length and non-empty")
    if any(not 0 <= x <= 1 or math.isnan(x) for x in p):
        raise ValueError("probabilities must be in [0, 1]")
    brier = mean((a - b) ** 2 for a, b in zip(p, y))
    base = mean(y)
    table = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        idx = [j for j, x in enumerate(p) if lo <= x < hi or (i == bins - 1 and x == 1.0)]
        if idx:
            table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(idx),
                          "mean_pred": round(mean(p[j] for j in idx), 4),
                          "observed": round(mean(y[j] for j in idx), 4)})
    return {"n": len(p), "brier": round(brier, 5), "brier_base_rate": round(mean((base - b) ** 2 for b in y), 5),
            "beats_base_rate": brier < mean((base - b) ** 2 for b in y), "table": table}


# -- decisions and the evaluation gate -----------------------------------------------------

def record_screen(ledger: Path, register: dict[str, Any], decision: str, ci: PairedInterval,
                  rationale: str, evidence: dict[str, Any]) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise RegisterError(f"decision must be one of {DECISIONS}")
    entry = {"type": "screen_decision", "experiment_id": register["experiment_id"],
             "register_sha256": register["register_sha256"], "decision": decision,
             "interval": ci.__dict__, "rationale": rationale, "evidence": evidence,
             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _append(ledger, entry)
    return entry


def open_evaluation(ledger: Path, register_path: Path, *, repo: Path) -> dict[str, Any]:
    register = load_register(register_path)
    entries = _entries(ledger, register["experiment_id"])
    screens = [e for e in entries if e["type"] == "screen_decision"]
    if not screens or screens[-1]["decision"] != "ADVANCE_TO_EVALUATION":
        raise RegisterError("evaluation is closed: no ADVANCE_TO_EVALUATION screen decision")
    if any(e["type"] == "evaluation_opened" for e in entries):
        raise RegisterError("evaluation was already opened once")
    for key, rel in (("candidate_policy", register["candidate_policy"]), ("calibration", register["calibration"])):
        if sha256_file(repo / rel) != register["input_sha256"][key]:
            raise RegisterError(f"{key} changed after the register was frozen")
    entry = {"type": "evaluation_opened", "experiment_id": register["experiment_id"],
             "register_sha256": register["register_sha256"],
             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _append(ledger, entry)
    return entry


def _append(ledger: Path, entry: dict[str, Any]) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def _entries(ledger: Path, experiment_id: str) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    return [e for e in (json.loads(x) for x in ledger.read_text().splitlines() if x.strip())
            if e.get("experiment_id") == experiment_id]
