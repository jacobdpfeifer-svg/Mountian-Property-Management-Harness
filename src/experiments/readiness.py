"""Canary readiness: every earlier stage, checked in one place (workstream 8).

`canary_readiness` reads evidence only. `validated_signoff` returns the
operator-written sign-off only when every gate passes; it never builds a
`CanaryAuthorization` (the canary stays inactive by construction). Nothing here
creates a sign-off or a write permit; a person writes both (docs/runbooks/CANARY.md).

Gates, in order:
  evaluation   the candidate's register has an evaluation verdict of PASS
  shadow       enough consecutive, healthy, reviewed shadow days; zero rate writes;
               the market anchor present on most nights (a canary priced off a
               missing anchor tests the fallback, not the model)
  field_plan   a frozen field-test plan names this experiment
  money        the spine holds settled, actual owner money for the canary home
               (realized profit cannot be measured without it)
  signoff      one home, named dates that are all treatment nights of the plan,
               bounded moves and write count, approver and rollback owner,
               a kill-switch test within 7 days, not expired
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.experiments import _entries, load_register
from src.experiments.field import arm_for, load_plan
from src.shadow import scorecard

SHADOW_MIN_DAYS = 28
SHADOW_MIN_STREAK = 14
SHADOW_MIN_HEALTHY = 0.90
SHADOW_MIN_REVIEWED = 0.80
SHADOW_MIN_ANCHORED = 0.50
MAX_PCT_MOVE = 0.10
MAX_WRITES = 14
KILL_TEST_MAX_AGE = timedelta(days=7)
SIGNOFF_FIELDS = ("authorization_id", "experiment_id", "plan_id", "property_id", "dates", "approver",
                  "rollback_owner", "max_abs_move", "max_pct_move", "max_writes", "floor_price",
                  "expires_at", "kill_switch_tested_at")


@dataclass
class Readiness:
    gates: list[tuple[str, bool, str]] = field(default_factory=list)
    signoff_sha256: str | None = None

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.gates.append((name, ok, detail))

    @property
    def ready(self) -> bool:
        return bool(self.gates) and all(ok for _, ok, _ in self.gates)

    def lines(self) -> list[str]:
        return [f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}" for name, ok, detail in self.gates]


def _ts(value: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else None


def canary_readiness(conn: sqlite3.Connection, *, ledger: Path, register_path: Path, plan_path: Path,
                     signoff_path: Path, now: datetime | None = None) -> Readiness:
    now = now or datetime.now(timezone.utc)
    r = Readiness()
    try:
        reg = load_register(register_path)
        # Only a verdict for this exact frozen register counts (the ledger is plain JSONL).
        verdicts = [e for e in _entries(ledger, reg["experiment_id"]) if e["type"] == "evaluation_decision"
                    and e.get("register_sha256") == reg["register_sha256"]]
        ok = bool(verdicts) and verdicts[-1]["decision"] == "PASS"
        r.add("evaluation", ok, f"{reg['experiment_id']}: "
              + (verdicts[-1]["decision"] if verdicts else "no evaluation verdict"))
    except Exception as exc:   # an unreadable register is a failed gate, not a crash
        reg = None
        r.add("evaluation", False, f"register unreadable: {exc}")

    try:
        signoff_bytes = Path(signoff_path).read_bytes()
        signoff = json.loads(signoff_bytes)
        r.signoff_sha256 = hashlib.sha256(signoff_bytes).hexdigest()
    except (OSError, ValueError) as exc:
        signoff = None
        r.add("signoff", False, f"no readable operator sign-off: {exc}")
    canary_home = signoff.get("property_id") if isinstance(signoff, dict) else None

    # Shadow evidence is judged for the canary home, not the portfolio.
    card = scorecard(conn, property_id=canary_home)
    problems = []
    if card["shadow_days"] < SHADOW_MIN_DAYS:
        problems.append(f"{card['shadow_days']} shadow days < {SHADOW_MIN_DAYS}")
    if card["longest_daily_streak"] < SHADOW_MIN_STREAK:
        problems.append(f"longest daily streak {card['longest_daily_streak']} < {SHADOW_MIN_STREAK}")
    if card["healthy_run_share"] < SHADOW_MIN_HEALTHY:
        problems.append(f"healthy share {card['healthy_run_share']:.0%} < {SHADOW_MIN_HEALTHY:.0%}")
    if card["reviewed_share"] < SHADOW_MIN_REVIEWED:
        problems.append(f"reviewed share {card['reviewed_share']:.0%} < {SHADOW_MIN_REVIEWED:.0%}")
    if card["rate_writes"]:
        problems.append(f"{card['rate_writes']} rate writes during shadow")
    if (card["anchored_share_median"] or 0) < SHADOW_MIN_ANCHORED:
        problems.append(f"market anchor on {card['anchored_share_median'] or 0:.0%} of nights < "
                        f"{SHADOW_MIN_ANCHORED:.0%} (fix scrape coverage first)")
    r.add("shadow", not problems, "; ".join(problems) or f"{card['shadow_days']} days, all thresholds met")

    try:
        plan = load_plan(plan_path)
        ok = reg is not None and plan["candidate_register"] == reg["experiment_id"]
        r.add("field_plan", ok, f"{plan['plan_id']} frozen" + ("" if ok else " but names another experiment"))
    except Exception as exc:
        plan = None
        r.add("field_plan", False, f"no frozen plan: {exc}")

    pid = canary_home
    try:
        settled = conn.execute(
            """SELECT COUNT(*) FROM fact_financial_ledger t WHERE t.property_id = ? AND t.basis = 'actual'
                   AND t.settlement_state = 'settled'
                   AND NOT EXISTS (SELECT 1 FROM fact_financial_ledger s WHERE s.supersedes_id = t.id)""",
            (pid,)).fetchone()[0] if pid else 0
        statements = conn.execute("SELECT COUNT(*) FROM fact_owner_statement WHERE property_id = ?",
                                  (pid,)).fetchone()[0] if pid else 0
    except sqlite3.OperationalError:
        settled = statements = 0
    r.add("money", settled > 0 and statements > 0,
          f"{settled} settled ledger lines, {statements} owner statements for {pid or 'no property'}")

    if signoff is not None:
        r.add("signoff", *_check_signoff(signoff, reg, plan, now))
    return r


def _check_signoff(s: Any, reg: dict | None, plan: dict | None, now: datetime) -> tuple[bool, str]:
    if not isinstance(s, dict):
        return False, "sign-off is not an object"
    missing = [k for k in SIGNOFF_FIELDS if k not in s]
    if missing:
        return False, f"sign-off missing {missing}"
    problems = []
    if reg is None or s["experiment_id"] != reg["experiment_id"]:
        problems.append("names another experiment")
    if plan is None or s["plan_id"] != plan["plan_id"]:
        problems.append("names another field plan")
    if not str(s["approver"]).strip() or not str(s["rollback_owner"]).strip():
        problems.append("approver and rollback owner are required")
    if not isinstance(s["dates"], list) or not s["dates"]:
        problems.append("names no dates")
    elif plan is not None:
        look = arm_for(plan)
        off = [d for d in s["dates"] if look(s["property_id"], d) != "treatment"]
        if off:
            problems.append(f"dates outside the plan's treatment nights: {off[:5]}")
    if float(s["max_pct_move"]) > MAX_PCT_MOVE or float(s["max_pct_move"]) <= 0:
        problems.append(f"max_pct_move must be in (0, {MAX_PCT_MOVE}]")
    if int(s["max_writes"]) > MAX_WRITES or int(s["max_writes"]) < 1:
        problems.append(f"max_writes must be in [1, {MAX_WRITES}]")
    if isinstance(s["dates"], list) and int(s["max_writes"]) < len(s["dates"]):
        problems.append("max_writes is below the number of dates")
    expires, tested = _ts(s["expires_at"]), _ts(s["kill_switch_tested_at"])
    if expires is None or expires <= now:
        problems.append("expired or no timezone on expires_at")
    if tested is None or now - tested > KILL_TEST_MAX_AGE or tested > now:
        problems.append("kill switch not tested in the last 7 days")
    return not problems, "; ".join(problems) or f"{s['authorization_id']} by {s['approver']}"


def validated_signoff(readiness: Readiness, signoff_path: Path) -> dict[str, Any]:
    """The operator's sign-off, returned only when every gate passes.

    This deliberately stops short of building a `CanaryAuthorization`: the canary
    stays inactive by construction (tests/security/test_canary.py). Activating it
    is a separate, reviewed change that passes this dict to the controller.
    """
    if not readiness.ready:
        raise PermissionError("canary not ready: " + " | ".join(l for l in readiness.lines() if l.startswith("[FAIL")))
    raw = Path(signoff_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != readiness.signoff_sha256:
        raise PermissionError("sign-off changed after the readiness check; re-run it")
    return dict(json.loads(raw))
