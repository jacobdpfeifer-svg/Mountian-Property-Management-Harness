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
- The code that prices and the code that simulates are hashed too
  (`code_sha256` over `CODE_PATHS`): a new code hash is a new candidate, so a
  board made by other code can never grade this register.
- Seeds any earlier board already ran are exposed: a register whose screen or
  evaluation seeds include one is refused at freeze (`exposed_seeds`).

It runs no simulation. Evaluation runs remain serial market-sim jobs under the
global run lock (src/proving_ground/run_lock.py).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

DECISIONS = ("ADVANCE_TO_EVALUATION", "REWORK", "REJECT")

# Code whose change makes a different candidate: all source, every policy, and the
# simulator with its scenarios. Hashing all of `src` (not a hand-picked list) is
# deliberate: the 2026-10-16 audit found comps, signals, runcache and db code that
# changes prices but sat outside the first list.
CODE_PATHS = ("src", "config/policies", "proving_ground_exam")
_CODE_SUFFIXES = (".py", ".yaml", ".yml", ".json", ".sql")   # docs do not change prices


class RegisterError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_sha256(repo: Path, paths: Iterable[str] = CODE_PATHS) -> str:
    """One hash over every source file under `paths` (path and content, sorted)."""
    files: list[Path] = []
    for rel in paths:
        p = repo / rel
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(f for f in p.rglob("*") if f.is_file() and f.suffix in _CODE_SUFFIXES
                         and "__pycache__" not in f.parts)
        else:
            raise RegisterError(f"code path {rel} does not exist")
    h = hashlib.sha256()
    for f in sorted(set(files)):
        h.update(f.relative_to(repo).as_posix().encode() + b"\0")
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def exposed_seeds(runs_root: Path) -> dict[str, set[int]]:
    """Seeds any run under `runs_root` has already produced, by scenario.

    Exposure is counted regardless of calibration or policy (anyone who read a
    seed's result has seen that world), and from every artifact a run leaves:
    finished boards (scoreboard.csv, manifest.json) and stopped or partial runs
    (results.jsonl checkpoints).
    """
    import csv

    out: dict[str, set[int]] = {}

    def add(row: Any) -> None:
        try:
            out.setdefault(str(row["scenario"]), set()).add(int(row["seed"]))
        except (KeyError, TypeError, ValueError):
            pass

    root = Path(runs_root).expanduser()
    for path in sorted(root.rglob("scoreboard.csv")):
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                add(row)
    for path in sorted(root.rglob("results.jsonl")):
        for line in path.read_text(errors="replace").splitlines():
            try:
                add(json.loads(line))
            except ValueError:
                continue
    for path in sorted(root.rglob("manifest.json")):
        try:
            rows = json.loads(path.read_text()).get("rows") or []
        except (ValueError, AttributeError):
            continue
        for row in rows:
            add(row)
    return out


def _check_unexposed(register: dict[str, Any], exposed: dict[str, set[int]]) -> None:
    clashes = []
    for part in ("screen", "evaluation"):
        seeds = set(register[part]["seeds"])
        for scenario in register[part]["scenarios"]:
            hit = seeds & exposed.get(scenario, set())
            if hit:
                clashes.append(f"{part} {scenario}: {sorted(hit)[:10]}{'…' if len(hit) > 10 else ''}")
    if clashes:
        raise RegisterError("seeds already exposed by earlier boards: " + "; ".join(clashes))


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def freeze_register(register: dict[str, Any], out: Path, *, repo: Path,
                    exposed: dict[str, set[int]] | None = None) -> dict[str, Any]:
    """Validate, hash inputs, and write the register once. Returns the frozen body.

    `exposed` (from `exposed_seeds`) refuses any seed an earlier board ran. Pass
    it for every new experiment; only the 2026-10-15 post-hoc register predates it.
    """
    required = ["experiment_id", "candidate_policy", "calibration", "objective", "comparator",
                "screen", "evaluation", "metrics", "stop_conditions"]
    missing = [k for k in required if k not in register]
    if "material_harm_margin" not in register and "harm_fraction" not in register:
        missing.append("material_harm_margin or harm_fraction")
    if missing:
        raise RegisterError(f"register missing {missing}")
    s_seeds, e_seeds = set(register["screen"]["seeds"]), set(register["evaluation"]["seeds"])
    if s_seeds & e_seeds:
        raise RegisterError(f"screen and evaluation seeds overlap: {sorted(s_seeds & e_seeds)}")
    if not register["evaluation"]["scenarios"]:
        raise RegisterError("evaluation scenarios must be declared before freezing")
    if out.exists():
        raise RegisterError(f"{out.name} is already frozen; a change needs a new experiment_id")
    if exposed is not None:
        _check_unexposed(register, exposed)
    body = dict(register)
    body["input_sha256"] = {
        "candidate_policy": sha256_file(repo / register["candidate_policy"]),
        "calibration": sha256_file(repo / register["calibration"]),
    }
    if "code_paths" in register:
        body["input_sha256"]["code"] = code_sha256(repo, register["code_paths"])
    body["seeds_checked_unexposed"] = exposed is not None
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


# Two-sided 95% Student-t quantiles by degrees of freedom (standard tables).
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262,
         10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110,
         18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
         26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def _t975(df: int) -> float:
    if df in _T975:
        return _T975[df]
    keys = sorted(_T975)
    for lo, hi in zip(keys, keys[1:]):
        if lo < df < hi:                       # interpolate in 1/df, which is near-linear
            w = (1 / df - 1 / hi) / (1 / lo - 1 / hi)
            return _T975[hi] + w * (_T975[lo] - _T975[hi])
    return 1.96


def paired_interval(deltas: Iterable[float], *, level: float = 0.95, **_ignored: Any) -> PairedInterval:
    """Student-t interval for the mean paired delta (candidate − comparator).

    Replaced the percentile bootstrap on 2026-10-16: at 5 seeds the bootstrap's
    nominal 95% covered only 72–83% (audit), so the screen was 2–3x looser than stated.
    """
    if level != 0.95:
        raise ValueError("only the preregistered 95% level is supported")
    d = [float(x) for x in deltas]
    if len(d) < 2:
        raise ValueError("need at least two paired seeds")
    m = mean(d)
    se = (sum((x - m) ** 2 for x in d) / (len(d) - 1)) ** 0.5 / len(d) ** 0.5
    half = _t975(len(d) - 1) * se
    return PairedInterval(len(d), round(m, 2), round(m - half, 2), round(m + half, 2),
                          round(min(d), 2), round(max(d), 2), sum(1 for x in d if x > 0))


def screen_decision(deltas: Iterable[float], *, margin: float, reject_below: float | None = None,
                    require_gain: bool = False) -> tuple[str, PairedInterval, str]:
    """Gate on screen seeds only.

    ADVANCE_TO_EVALUATION: the interval's lower bound is above −margin, and with
    `require_gain` (every register from EXP-PACE-V3 on) the mean delta is above 0:
    a candidate must beat the comparator, not merely not lose to it.
    REJECT: the interval's upper bound is below −reject_below (clear, large harm).
    REWORK: anything else.
    """
    ci = paired_interval(deltas)
    if require_gain and ci.lo > -margin and ci.mean <= 0:
        return "REWORK", ci, f"no gain: mean {ci.mean:+,.0f} <= 0 (harm excluded, but it does not beat the comparator)"
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
    if "code" in register["input_sha256"] and \
            code_sha256(repo, register["code_paths"]) != register["input_sha256"]["code"]:
        raise RegisterError("code changed after the register was frozen; that is a new candidate")
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


# -- board provenance ---------------------------------------------------------------

LEGACY_REGISTERS = frozenset({"EXP-PACE-V2-001"})   # frozen before code hashing existed


def _aware(value: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else None


def board_provenance_problem(reg: dict[str, Any], *boards: Path, candidate: bool = False,
                             not_before: datetime | None = None) -> str | None:
    """Why a board may not grade this register, or None. Fails closed.

    Every board: frozen code hash, frozen calibration file, no sensitivity overlay,
    a clean tracked tree (False, not merely absent), and a first start after the
    freeze (and after `not_before`, e.g. the evaluation_opened time). Candidate
    boards also need the frozen candidate policy.
    """
    want = reg["input_sha256"].get("code")
    if want is None:
        if reg.get("experiment_id") in LEGACY_REGISTERS:
            return None
        return "register has no code hash; freeze it with scripts/freeze_experiment.py"
    frozen = _aware(reg.get("frozen_at"))
    floor = max(t for t in (frozen, not_before) if t is not None) if (frozen or not_before) else None
    for board in boards:
        raw = json.loads((Path(board) / "run_config.json").read_text())
        cfg = raw.get("config") or raw
        name = Path(board).name
        if cfg.get("code_sha256") != want:
            return f"{name} was made by different code than the register froze"
        if cfg.get("calibration_file_sha256") != reg["input_sha256"]["calibration"]:
            return f"{name} used a different calibration file"
        if cfg.get("sensitivity_label") is not None:
            return f"{name} ran under a sensitivity overlay ({cfg.get('sensitivity_label')})"
        if candidate and cfg.get("engine_policy_sha256") != reg["input_sha256"]["candidate_policy"]:
            return f"{name} ran a different policy than the frozen candidate"
        if cfg.get("git_dirty_tracked") is not False:
            return f"{name} does not prove a clean tracked tree"
        started = _aware(raw.get("first_started_at") or raw.get("started_at"))
        if started is None:
            return f"{name} has no start time"
        if floor is not None and started < floor:
            return f"{name} started before the register was frozen or evaluation was opened"
    return None


# -- evaluation gate (workstream 5) ------------------------------------------------------

def evaluation_decision(register: dict[str, Any], candidate_rows: list[dict[str, Any]],
                        comparator_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The preregistered evaluation verdict from paired manifest rows.

    Every (scenario, seed) the register names must be present for both policies.
    PASS needs, on paired owner-net deltas (candidate - comparator):
      - superiority on each `primary_scenarios` world: interval lower bound > 0;
      - non-inferiority on every declared world: lower bound > -harm_fraction x
        the comparator's mean owner net in that world;
      - no home whose mean delta, in any world, is worse than -segment_fraction of
        its comparator mean (owner_net_by_property).
    Anything else is FAIL, with every reason listed.
    """
    ev = register["evaluation"]
    seeds, scenarios = set(ev["seeds"]), list(ev["scenarios"])
    primary = set(ev.get("primary_scenarios", ["normal"]))
    harm_f, seg_f = float(register["harm_fraction"]), float(register["segment_fraction"])

    def index(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
        return {(r["scenario"], int(r["seed"])): r for r in rows
                if r["scenario"] in scenarios and int(r["seed"]) in seeds}

    cand, comp = index(candidate_rows), index(comparator_rows)
    want = {(s, n) for s in scenarios for n in seeds}
    missing = sorted(want - (set(cand) & set(comp)))
    if missing:
        return {"decision": "INCOMPLETE", "missing": [f"{s}/{n}" for s, n in missing[:20]],
                "n_missing": len(missing)}
    reasons, worlds = [], {}
    for s in scenarios:
        keys = sorted(k for k in want if k[0] == s)
        deltas = [float(cand[k]["owner_net"]) - float(comp[k]["owner_net"]) for k in keys]
        base = mean(float(comp[k]["owner_net"]) for k in keys)
        ci = paired_interval(deltas)
        margin = harm_f * base
        homes = {}
        names = sorted(set().union(*((cand[k].get("owner_net_by_property") or {}).keys() for k in keys),
                                   *((comp[k].get("owner_net_by_property") or {}).keys() for k in keys)))
        for pid in names:
            have = [k for k in keys if pid in (cand[k].get("owner_net_by_property") or {})
                    and pid in (comp[k].get("owner_net_by_property") or {})]
            if len(have) != len(keys):
                reasons.append(f"{s}: {pid} missing from some boards; its harm cannot be judged")
                continue
            d = mean(float(cand[k]["owner_net_by_property"][pid]) - float(comp[k]["owner_net_by_property"][pid])
                     for k in keys)
            b = mean(float(comp[k]["owner_net_by_property"][pid]) for k in keys)
            # A home's margin never shrinks below its fair share of the world margin, so a
            # home with a zero or negative baseline is still checked (2026-10-16 audit).
            home_margin = max(seg_f * abs(b), seg_f * abs(base) / len(names))
            homes[pid] = {"mean_delta": round(d, 2), "comparator_mean": round(b, 2),
                          "margin": round(home_margin, 2)}
            if d < -home_margin:
                reasons.append(f"{s}: {pid} mean delta {d:+,.0f} worse than -{home_margin:,.0f}")
        if not homes:
            reasons.append(f"{s}: no per-home owner net in the boards; segment harm cannot be judged")
        if s in primary and ci.lo <= 0:
            reasons.append(f"{s}: not superior (lower bound {ci.lo:+,.0f} <= 0)")
        if ci.lo <= -margin:
            reasons.append(f"{s}: harm not excluded (lower bound {ci.lo:+,.0f} <= -{margin:,.0f})")
        worlds[s] = {"interval": ci.__dict__, "margin": round(margin, 2), "homes": homes}
    return {"decision": "PASS" if not reasons else "FAIL", "reasons": reasons, "worlds": worlds}
