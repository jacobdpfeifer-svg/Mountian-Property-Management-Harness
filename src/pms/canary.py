"""Scoped canary write controller with read-back and rollback (06K). INACTIVE.

Nothing in this repository creates a `CanaryAuthorization` for a real write,
the real kill switch blocks every write without an operator-issued permit
(src/security/kill_switch.py), and a live adapter additionally requires the
authorization to be marked operator-signed. Tests drive the controller with an
injected fake adapter and an injected switch; that is the only writer used here.

Sequence, with an abort (and rollback of anything already written) at each step:

  authorize -> scope -> health/readiness -> snapshot -> dry-run diff -> movement
  caps -> per write: kill switch, idempotency, write, read-back price,
  read-back non-price fields -> done

Every step appends to an immutable receipt (list of events) returned to the
caller; the caller persists it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Protocol

from src.security.kill_switch import SwitchState, state as real_switch_state
from src.security.scope import PortfolioScope

NON_PRICE_FIELDS = ("status", "min_stay", "blocked")


class CanaryAdapter(Protocol):
    name: str
    live: bool

    def fetch_calendar(self, property_id: str, start: date, end: date) -> list[dict[str, Any]]: ...

    def push_rate(self, property_id: str, stay_date: date, price: float,
                  min_stay: int | None = None) -> Any: ...


@dataclass(frozen=True)
class CanaryAuthorization:
    """The operator's written scope. Must exist before any canary call."""
    authorization_id: str
    property_id: str
    dates: tuple[date, ...]
    approver: str
    rollback_owner: str
    max_abs_move: float
    max_pct_move: float
    max_writes: int
    expires_at: datetime
    floor_price: float                 # operator's minimum nightly rate for these dates
    operator_signed: bool = False      # required for a live adapter; never set in this repo


@dataclass(frozen=True)
class CanaryChange:
    stay_date: date
    new_price: float


class CanaryAbort(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass
class CanaryResult:
    status: str                              # completed | aborted | aborted_rollback_failed
    abort_code: str | None
    receipt: list[dict[str, Any]] = field(default_factory=list)
    written: list[str] = field(default_factory=list)
    rolled_back: list[str] = field(default_factory=list)


def idempotency_key(auth: CanaryAuthorization, change: CanaryChange) -> str:
    raw = f"{auth.authorization_id}|{auth.property_id}|{change.stay_date}|{change.new_price:.2f}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class CanaryController:
    def __init__(self, adapter: CanaryAdapter, scope: PortfolioScope, *,
                 switch: Callable[[str], SwitchState] = real_switch_state,
                 completed_keys: set[str] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.adapter, self.scope, self.switch, self.now = adapter, scope, switch, now
        self.completed_keys = completed_keys if completed_keys is not None else set()

    # -- helpers ------------------------------------------------------------------------
    def _log(self, result: CanaryResult, step: str, **detail: Any) -> None:
        result.receipt.append({"at": self.now().isoformat(timespec="seconds"), "step": step,
                               **json.loads(json.dumps(detail, default=str))})

    def _read(self, auth: CanaryAuthorization, d: date) -> dict[str, Any]:
        days = self.adapter.fetch_calendar(auth.property_id, d, d) or []
        for day in days:
            if isinstance(day, dict) and str(day.get("date", ""))[:10] == d.isoformat():
                return day
        raise CanaryAbort("SNAPSHOT_MISSING", d.isoformat())

    # -- preconditions --------------------------------------------------------------------
    def _preflight(self, auth: CanaryAuthorization | None, changes: list[CanaryChange],
                   health: str, readiness: dict[date, str]) -> CanaryAuthorization:
        if auth is None:
            raise CanaryAbort("NO_AUTHORIZATION")
        if not auth.approver.strip() or not auth.rollback_owner.strip():
            raise CanaryAbort("NO_NAMED_APPROVER")
        if self.now() >= auth.expires_at:
            raise CanaryAbort("AUTHORIZATION_EXPIRED")
        if getattr(self.adapter, "live", False) and not auth.operator_signed:
            raise CanaryAbort("LIVE_ADAPTER_UNSIGNED")
        if not self.scope.check_property(auth.property_id).allowed:
            raise CanaryAbort("SCOPE_MISMATCH", auth.property_id)
        if not changes:
            raise CanaryAbort("NO_CHANGES")
        if len(changes) > auth.max_writes:
            raise CanaryAbort("MAX_WRITES_EXCEEDED", f"{len(changes)} > {auth.max_writes}")
        if len({c.stay_date for c in changes}) != len(changes):
            raise CanaryAbort("DUPLICATE_DATE")
        stray = [c.stay_date.isoformat() for c in changes if c.stay_date not in auth.dates]
        if stray:
            raise CanaryAbort("DATE_NOT_AUTHORIZED", ",".join(stray))
        if health != "handle":
            raise CanaryAbort("STALE_HEALTH", health)
        blocked = [d.isoformat() for d, r in readiness.items() if r != "ready"]
        if blocked or any(c.stay_date not in readiness for c in changes):
            raise CanaryAbort("OPERATIONAL_RESTRICTION", ",".join(blocked) or "readiness missing")
        gate = self.switch(auth.property_id)
        if not gate.writes_allowed:
            raise CanaryAbort("KILL_SWITCH", gate.reason)
        return auth

    # -- run ------------------------------------------------------------------------------
    def run(self, auth: CanaryAuthorization | None, changes: list[CanaryChange], *,
            health: str, readiness: dict[date, str], dry_run_only: bool = False) -> CanaryResult:
        result = CanaryResult("aborted", None)
        snapshot: dict[date, dict[str, Any]] = {}
        try:
            auth = self._preflight(auth, changes, health, readiness)
            self._log(result, "authorized", authorization_id=auth.authorization_id,
                      approver=auth.approver, property_id=auth.property_id)
            for c in changes:
                snapshot[c.stay_date] = dict(self._read(auth, c.stay_date))
            self._log(result, "snapshot", days={d.isoformat(): s for d, s in snapshot.items()})
            diff = []
            for c in changes:
                before = snapshot[c.stay_date]
                if before.get("status") != "available" or before.get("blocked"):
                    raise CanaryAbort("NIGHT_NOT_AVAILABLE", c.stay_date.isoformat())
                old = float(before["price"])
                move = c.new_price - old
                if not c.new_price > 0 or c.new_price + 0.01 < auth.floor_price:
                    raise CanaryAbort("BELOW_FLOOR", f"{c.stay_date} {c.new_price:.2f} < {auth.floor_price:.2f}")
                if abs(move) > auth.max_abs_move + 1e-9 or \
                        abs(move) / old > auth.max_pct_move + 1e-9:
                    raise CanaryAbort("MOVE_CAP_EXCEEDED", f"{c.stay_date} {old:.2f}->{c.new_price:.2f}")
                diff.append({"date": c.stay_date.isoformat(), "old": old, "new": c.new_price})
            self._log(result, "dry_run_diff", diff=diff)
            if dry_run_only:
                result.status = "dry_run"
                return result
            for c in changes:
                gate = self.switch(auth.property_id)
                if not gate.writes_allowed:
                    raise CanaryAbort("KILL_SWITCH", gate.reason)
                key = idempotency_key(auth, c)
                if key in self.completed_keys:
                    self._log(result, "idempotent_skip", date=c.stay_date, key=key)
                    continue
                res = self._guarded_push(auth, c.stay_date, c.new_price, snapshot)
                result.written.append(c.stay_date.isoformat())
                if not getattr(res, "ok", False):
                    raise CanaryAbort("WRITE_FAILED", getattr(res, "error", "") or "")
                after = self._read(auth, c.stay_date)
                if abs(float(after.get("price", -1)) - c.new_price) > 0.01:
                    raise CanaryAbort("READBACK_MISMATCH", f"{c.stay_date} got {after.get('price')}")
                changed = [f for f in NON_PRICE_FIELDS if after.get(f) != snapshot[c.stay_date].get(f)]
                if changed:
                    raise CanaryAbort("NON_PRICE_FIELD_CHANGED", f"{c.stay_date} {changed}")
                self.completed_keys.add(key)
                self._log(result, "written_and_verified", date=c.stay_date, price=c.new_price, key=key)
            result.status, result.abort_code = "completed", None
            return result
        except CanaryAbort as exc:
            result.abort_code = exc.code
            self._log(result, "abort", code=exc.code, detail=str(exc))
            if result.written:
                self._rollback(result, auth, snapshot)
            return result

    def _guarded_push(self, auth: CanaryAuthorization, d: date, price: float,
                      snapshot: dict[date, dict[str, Any]], *, rollback: bool = False) -> Any:
        """The canary's only adapter write. Re-checks the final boundary every time.

        A forward write must be finite, positive, at or above the floor, inside
        the authorized dates, and within the move caps of the snapshot price. A
        rollback may only restore the exact snapshot price.
        """
        import math

        if d not in auth.dates or d not in snapshot:
            raise CanaryAbort("DATE_NOT_AUTHORIZED", d.isoformat())
        old = float(snapshot[d]["price"])
        if not math.isfinite(price) or price <= 0:
            raise CanaryAbort("BOUNDARY_REJECTED", f"{d} non-positive price")
        if rollback:
            if abs(price - old) > 0.01:
                raise CanaryAbort("BOUNDARY_REJECTED", f"{d} rollback must restore {old:.2f}")
        else:
            if price + 0.01 < auth.floor_price:
                raise CanaryAbort("BELOW_FLOOR", f"{d} {price:.2f}")
            if abs(price - old) > auth.max_abs_move + 1e-9 or abs(price - old) / old > auth.max_pct_move + 1e-9:
                raise CanaryAbort("MOVE_CAP_EXCEEDED", f"{d} {old:.2f}->{price:.2f}")
        return self.adapter.push_rate(auth.property_id, d, price)

    def _rollback(self, result: CanaryResult, auth: CanaryAuthorization | None,
                  snapshot: dict[date, dict[str, Any]]) -> None:
        assert auth is not None
        failed: list[str] = []
        for iso in result.written:
            d = date.fromisoformat(iso)
            prior = float(snapshot[d]["price"])
            try:
                res = self._guarded_push(auth, d, prior, snapshot, rollback=True)
                after = self._read(auth, d)
                ok = getattr(res, "ok", False) and abs(float(after.get("price", -1)) - prior) <= 0.01
            except Exception as exc:  # rollback must report, never raise past the receipt
                ok = False
                self._log(result, "rollback_error", date=iso, error=type(exc).__name__)
            (result.rolled_back if ok else failed).append(iso)
        self._log(result, "rollback", restored=result.rolled_back, failed=failed)
        result.status = "aborted_rollback_failed" if failed else "aborted"
