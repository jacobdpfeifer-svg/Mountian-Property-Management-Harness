"""CLI commands for the path to realized profit: data spine, shadow, field test, canary readiness.

None of these writes a rate. `canary-readiness` only reports; it never authorizes.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from src.db import connect, init_db
from src.db.migrations import apply_migrations
from src.security.scope import EXPECTED_PROPERTY_IDS

ROOT = Path(__file__).resolve().parents[2]


def _conn(args: argparse.Namespace):
    init_db(args.db)
    conn = connect(args.db)
    apply_migrations(conn)
    return conn


def cmd_spine_backfill_guesty(args: argparse.Namespace) -> int:
    from src.data_spine.backfill import backfill_guesty
    from src.pms.guesty import LOCKED_LISTING_PROPERTY_IDS, GuestyClient

    conn = _conn(args)
    rep = backfill_guesty(conn, GuestyClient(), property_by_listing=dict(LOCKED_LISTING_PROPERTY_IDS),
                          scope=EXPECTED_PROPERTY_IDS, check_in_from=date.fromisoformat(args.since),
                          calendar_days=args.calendar_days)
    print("\n".join(rep.summary()))
    print("Guesty writes: 0 (read-only client)")
    return 1 if rep.quarantined else 0


def cmd_spine_import(args: argparse.Namespace) -> int:
    from src.data_spine.backfill import import_csv

    rep = import_csv(_conn(args), Path(args.csv), Path(args.mapping), scope=EXPECTED_PROPERTY_IDS)
    print("\n".join(rep.summary()))
    for r in rep.results:
        for q in r.quarantined[:10]:
            print(f"  quarantined {q['entity_key']}: {q['detail']}")
    return 1 if rep.quarantined else 0


def cmd_shadow_day(args: argparse.Namespace) -> int:
    from src.config import DEFAULT_POLICY_PATH, load_policy
    from src.experiments import code_sha256
    from src.experiments.field import arm_for, load_plan
    from src.guardrails import assess_data_health
    from src.shadow import capture_outcomes, file_sha256, run_shadow_day, scorecard

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    conn = _conn(args)
    policy = load_policy()
    arm = arm_for(load_plan(Path(args.plan))) if args.plan else None
    props = [p.strip() for p in args.property.split(",")] if args.property else sorted(EXPECTED_PROPERTY_IDS)
    for pid in props:
        health = assess_data_health(conn, policy, property_ids=[pid], as_of=as_of)
        day = run_shadow_day(conn, as_of=as_of, property_id=pid, health=health,
                             policy_sha256=file_sha256(Path(args.policy_file or DEFAULT_POLICY_PATH)),
                             code_sha256=code_sha256(ROOT),
                             scope=EXPECTED_PROPERTY_IDS, arm_for=arm)
        print(f"{pid}: {day.queued} nights queued, {day.stale} skipped as stale (run `recommend` first), "
              f"health {day.health_level}, anchored {day.anchored_share if day.anchored_share is not None else 'n/a'}")
    print(f"outcomes captured: {capture_outcomes(conn, as_of=as_of)}")
    print(json.dumps(scorecard(conn), indent=1))
    print("Guesty writes: 0")
    return 0


def cmd_field_freeze(args: argparse.Namespace) -> int:
    from src.experiments.field import PlanError, freeze_plan

    try:
        body = freeze_plan(json.loads(Path(args.spec).read_text()), Path(args.out))
    except PlanError as exc:
        print(f"field-freeze: {exc}", file=sys.stderr)
        return 2
    print(f"frozen {body['plan_id']} plan_sha256={body['plan_sha256']}")
    return 0


def cmd_field_analyse(args: argparse.Namespace) -> int:
    from src.experiments.field import analyse, block_outcomes, load_plan

    from src.experiments.field import check_stop_rules

    plan = load_plan(Path(args.plan))
    conn = _conn(args)
    res = analyse(block_outcomes(conn, plan), plan,
                  fired_stop_rules=check_stop_rules(conn, plan, as_of=date.today()))
    print(json.dumps(res, indent=1, default=str))
    return {"PROVEN": 0, "INCONCLUSIVE": 3, "HARM": 1}[res["decision"]]


def cmd_field_stop_check(args: argparse.Namespace) -> int:
    from src.experiments.field import check_stop_rules, load_plan

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    fired = check_stop_rules(_conn(args), load_plan(Path(args.plan)), as_of=as_of)
    for f in fired:
        print(f"STOP: {f}")
    if not fired:
        print("no stop rule fired")
    return 1 if fired else 0


def cmd_canary_readiness(args: argparse.Namespace) -> int:
    from src.experiments.readiness import canary_readiness

    r = canary_readiness(_conn(args), ledger=Path(args.ledger), register_path=Path(args.register),
                         plan_path=Path(args.plan), signoff_path=Path(args.signoff).expanduser())
    print("\n".join(r.lines()))
    print("READY" if r.ready else "NOT READY")
    return 0 if r.ready else 1


def register(sub: argparse._SubParsersAction) -> None:
    s = sub.add_parser("spine-backfill-guesty", help="Read-only Guesty history into the data spine")
    s.add_argument("--since", default="2021-01-01", help="Earliest check-in to pull")
    s.add_argument("--calendar-days", type=int, default=365)
    s.set_defaults(func=cmd_spine_backfill_guesty)

    s = sub.add_parser("spine-import", help="Load an accounting/statement/ops CSV through a mapping file")
    s.add_argument("--csv", required=True)
    s.add_argument("--mapping", required=True, help="config/data_mapping/<name>.yaml")
    s.set_defaults(func=cmd_spine_import)

    s = sub.add_parser("shadow-day", help="Queue today's recommendations for review; capture outcomes")
    s.add_argument("--as-of")
    s.add_argument("--property", help="Comma-separated; default all three homes")
    s.add_argument("--plan", help="Frozen field plan, to label treatment/control nights")
    s.add_argument("--policy-file", help="Policy the day's `recommend` run used (recorded by hash)")
    s.set_defaults(func=cmd_shadow_day)

    s = sub.add_parser("field-freeze", help="Freeze a field-test plan (before any canary)")
    s.add_argument("--spec", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_field_freeze)

    s = sub.add_parser("field-analyse", help="Preregistered realized owner-net analysis")
    s.add_argument("--plan", required=True)
    s.set_defaults(func=cmd_field_analyse)

    s = sub.add_parser("field-stop-check", help="Leading-indicator stop rules for a running field test")
    s.add_argument("--plan", required=True)
    s.add_argument("--as-of")
    s.set_defaults(func=cmd_field_stop_check)

    s = sub.add_parser("canary-readiness", help="Check every gate before a canary (reports only)")
    s.add_argument("--ledger", default="docs/reports/final_delivery/experiments/decisions.jsonl")
    s.add_argument("--register", required=True)
    s.add_argument("--plan", required=True)
    s.add_argument("--signoff", default="~/.wp-price/control/canary_signoff.json")
    s.set_defaults(func=cmd_canary_readiness)
