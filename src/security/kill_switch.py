"""Global, fail-closed write kill switch.

A live rate write is permitted only when ALL of these hold at the moment of the
call (checked at the final adapter boundary, `GuestyClient.set_rate`, and again
by `push_recommendations` and the canary controller):

1. no `KILL` file exists in the control directory;
2. `write_permit.json` exists, parses, and says ``"writes_enabled": true``;
3. the permit names this environment, which must be ``production``;
4. the permit has not expired and names the property being written;
5. `WP_PRICE_ENV=production`.

Anything missing, unreadable, malformed, or expired blocks the write. Engaging
the switch (`python -m src.security.kill_switch engage`) always works and needs
no permit; there is deliberately no command that creates a permit.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CONTROL_DIR_ENV = "WP_PRICE_CONTROL_DIR"
KILL_FILE = "KILL"
PERMIT_FILE = "write_permit.json"


class WriteBlocked(RuntimeError):
    """A live write was refused by the kill switch or permit check."""


def control_dir() -> Path:
    raw = os.environ.get(CONTROL_DIR_ENV)
    return Path(raw).expanduser() if raw else Path.home() / ".wp-price" / "control"


@dataclass(frozen=True)
class SwitchState:
    writes_allowed: bool
    reason: str
    permit_id: str | None = None


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def state(property_id: str | None = None, *, now: datetime | None = None) -> SwitchState:
    """Evaluate the switch. Never raises: every failure is a blocked state."""
    from src.security.environment import Environment, current_environment

    try:
        directory = control_dir()
        if (directory / KILL_FILE).exists():
            return SwitchState(False, "kill switch engaged")
        if current_environment() is not Environment.PRODUCTION:
            return SwitchState(False, f"environment is {current_environment().value}, not production")
        permit_path = directory / PERMIT_FILE
        if not permit_path.exists():
            return SwitchState(False, "no write permit")
        try:
            permit = json.loads(permit_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return SwitchState(False, "write permit unreadable")
        if not isinstance(permit, dict):
            return SwitchState(False, "write permit malformed")
        permit_id = permit.get("permit_id") if isinstance(permit.get("permit_id"), str) else None
        if permit.get("writes_enabled") is not True:
            return SwitchState(False, "write permit does not enable writes", permit_id)
        if permit.get("environment") != Environment.PRODUCTION.value:
            return SwitchState(False, "write permit is not for production", permit_id)
        if not permit_id or not isinstance(permit.get("approved_by"), str) or not permit["approved_by"]:
            return SwitchState(False, "write permit lacks permit_id/approved_by", permit_id)
        expires = _parse_time(permit.get("expires_at"))
        if expires is None:
            return SwitchState(False, "write permit expiry missing or not timezone-aware", permit_id)
        if (now or datetime.now(timezone.utc)) >= expires:
            return SwitchState(False, "write permit expired", permit_id)
        scope = permit.get("property_ids")
        if not isinstance(scope, list) or not scope:
            return SwitchState(False, "write permit names no properties", permit_id)
        if property_id is not None and property_id not in scope:
            return SwitchState(False, f"write permit does not cover {property_id}", permit_id)
        return SwitchState(True, "permitted", permit_id)
    except Exception as exc:  # fail closed on anything unexpected
        return SwitchState(False, f"kill switch check failed: {type(exc).__name__}")


def assert_write_permitted(property_id: str | None = None) -> SwitchState:
    current = state(property_id)
    if not current.writes_allowed:
        raise WriteBlocked(current.reason)
    return current


def engage(reason: str) -> Path:
    directory = control_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / KILL_FILE
    path.write_text(json.dumps({
        "engaged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason": reason,
    }) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kill_switch", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    eng = sub.add_parser("engage")
    eng.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "engage":
        print(f"kill switch engaged: {engage(args.reason)}")
        return 0
    current = state()
    print(json.dumps({"writes_allowed": current.writes_allowed, "reason": current.reason,
                      "control_dir": str(control_dir())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
