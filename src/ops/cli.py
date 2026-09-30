"""`wp-price ops ...` — operations data, shadow economics, readiness, incidents."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

from src.db import connect
from src.utils import parse_date


def _dates(args: argparse.Namespace) -> tuple[date, date]:
    start = parse_date(args.start) if getattr(args, "start", None) else date.today() - timedelta(days=90)
    end = parse_date(args.end) if getattr(args, "end", None) else date.today()
    return start, end


def _as_of(args: argparse.Namespace) -> date:
    return parse_date(args.as_of) if getattr(args, "as_of", None) else date.today()


def _print_result(result) -> int:
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.status in ("ok", "partial") else 1


def cmd_ops_sources(args: argparse.Namespace) -> int:
    from src.ops.sources import status

    with connect(args.db) as conn:
        for s in status(conn):
            flag = "configured" if s.configured else "UNCONFIGURED"
            last = s.last_run or {}
            tail = (f" | last {last.get('status')} {last.get('started_at')} "
                    f"accepted={last.get('accepted')} rejected={last.get('rejected')}") if last else ""
            print(f"{s.name:<13} {flag:<13} {s.detail}{tail}")
    return 0


def cmd_ops_profiles(args: argparse.Namespace) -> int:
    from src.ops.profiles import load_profiles, store_profiles

    profiles = load_profiles()
    with connect(args.db) as conn:
        created = store_profiles(conn, profiles)
    for pid, p in profiles.items():
        print(f"{pid:<15} {p.version} basis={p.basis} zone={p.access_zone} "
              f"worker_min={p.worker_minutes():.0f} elapsed_min={p.elapsed_minutes():.0f} "
              f"est_cost=${p.estimated_cost():,.0f} (snow ${p.estimated_cost(snow=True):,.0f})")
    print(f"{created} new profile version(s) stored")
    return 0


def cmd_ops_import(args: argparse.Namespace) -> int:
    start, end = _dates(args)
    with connect(args.db) as conn:
        if args.source == "csv":
            if not args.file:
                print("--file is required for --source csv", file=sys.stderr)
                return 2
            from src.ops.sources.csv_import import import_csv

            return _print_result(import_csv(conn, args.file, kind=args.kind, preset=args.preset))
        if args.source == "telemetry":
            if not args.file:
                print("--file is required for --source telemetry", file=sys.stderr)
                return 2
            from src.ops.sources.telemetry import import_telemetry

            return _print_result(import_telemetry(conn, args.file))
        if args.source == "manual":
            from src.ops.sources.manual import import_manual

            return _print_result(import_manual(conn, start, end, as_of=_as_of(args)))
        if args.source == "webhooks":
            from src.ops.sources.webhooks import import_task_webhooks

            return _print_result(import_task_webhooks(conn))
        from src.ops.sources import api_import

        fn = {"guesty_tasks": api_import.import_guesty_tasks,
              "breezeway": api_import.import_breezeway,
              "turno": api_import.import_turno}[args.source]
        return _print_result(fn(conn, start, end))


def cmd_ops_report(args: argparse.Namespace) -> int:
    from src.ops.shadow import build_report, render_text

    start, end = parse_date(args.start), parse_date(args.end)
    props = [p.strip() for p in args.property.split(",")] if args.property else None
    with connect(args.db) as conn:
        report = build_report(conn, start, end, as_of=_as_of(args), property_ids=props)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, default=str))
    else:
        print(render_text(report))
    return 0


def cmd_ops_capacity(args: argparse.Namespace) -> int:
    from src.ops.shadow import build_report

    day = parse_date(args.date)
    with connect(args.db) as conn:
        report = build_report(conn, day, day, as_of=_as_of(args))
    if not report.capacity:
        print(f"No turns on {day}.")
        return 0
    for c in report.capacity:
        u = "?" if c["utilization"] is None else f"{c['utilization']:.0%}"
        print(f"{c['service_date']} {c['access_zone']:<11} turns={c['turns']} "
              f"committed={c['committed_worker_minutes']:.0f} / available={c['available_worker_minutes']:.0f} "
              f"({u}) [{c['flag']}] source={c['available_source']}")
    for t in report.turns:
        print(f"  {t['property_id']:<15} slack={t['slack_minutes']} P(ready)={t['ready']['p']:.2f} "
              f"{'SAME-DAY' if t['same_day'] else ''}")
    return 0


# ------------------------------------------------------------- readiness

def cmd_ops_event_add(args: argparse.Namespace) -> int:
    from datetime import datetime

    from src.ops import AssetEvent
    from src.ops.db import record_asset_event
    from src.ops.readiness import ReadinessError, transition

    observed = args.observed_at or datetime.now().replace(microsecond=0).isoformat()
    reading = json.loads(args.reading) if args.reading else {}
    with connect(args.db) as conn:
        event_id, created = record_asset_event(conn, AssetEvent(
            property_id=args.property, system_type=args.system, observed_at=observed,
            severity=args.severity, source_type=args.source_type,
            effective_from=args.effective_from, effective_to=args.effective_to,
            source_ref=args.ref, reading=reading, verified_by=args.verified_by,
        ))
        conn.commit()
        print(f"event {event_id} {'recorded' if created else 'already recorded'}")
        if args.state:
            try:
                st = transition(
                    conn, args.property, args.state, evidence_event_id=event_id,
                    actor=args.actor, at=observed,
                    effective_from=parse_date(args.effective_from) if args.effective_from else None,
                    effective_to=parse_date(args.effective_to) if args.effective_to else None,
                    note=args.note,
                )
            except ReadinessError as exc:
                print(f"refused: {exc}", file=sys.stderr)
                return 1
            print(f"{args.property} → {st.state} (window {st.effective_from}..{st.effective_to or 'open'})")
    return 0


def cmd_ops_readiness(args: argparse.Namespace) -> int:
    from src.ops.profiles import load_ops_policy, load_profiles
    from src.ops.readiness import RESTRICTING, current_state, revenue_at_risk, scan_signal_risk

    as_of = _as_of(args)
    policy = load_ops_policy()
    pids = list(load_profiles())
    with connect(args.db) as conn:
        if args.scan_signals:
            for c in scan_signal_risk(conn, as_of, policy, pids):
                print(f"auto at_risk: {c}")
        for pid in pids:
            st = current_state(conn, pid, as_of)
            line = f"{pid:<15} {st.state:<24} since {st.since or '-'} by {st.actor or '-'}"
            if st.state in RESTRICTING:
                start = st.effective_from or as_of
                end = st.effective_to or (start + timedelta(days=14))
                risk = revenue_at_risk(conn, pid, start, end, policy)
                line += (f" | window {start}..{st.effective_to or 'open'} "
                         f"revenue at risk ${risk['total']:,.0f} ({len(risk['reservations'])} stay(s))")
            print(line)
    return 0


# ------------------------------------------------------------- incidents

def cmd_ops_incidents(args: argparse.Namespace) -> int:
    from src.ops import incidents as inc

    with connect(args.db) as conn:
        if args.incidents_command == "scan":
            found = inc.scan(conn, _as_of(args))
            for i in found:
                print(f"{i.incident_id} {i.incident_type} {i.window_start}..{i.window_end} "
                      f"[{i.severity}] {'new' if i.created else 'existing'}")
            if not found:
                print("No thresholds crossed.")
            return 0
        if args.incidents_command == "list":
            for row in inc.list_incidents(conn, status=args.status):
                print(f"{row['incident_id']} {row['incident_type']:<24} {row['window_start']}..{row['window_end']} "
                      f"[{row['severity']}] {row['status']}")
            return 0
        if args.incidents_command == "show":
            print(json.dumps(inc.show(conn, args.incident_id), indent=2, default=str))
            return 0
        if args.incidents_command == "approve":
            try:
                out = inc.approve(conn, args.incident_id, args.action, actor=args.actor,
                                  live=args.confirm_live_write, adapter=args.adapter)
            except (inc.ForbiddenAction, inc.IncidentError) as exc:
                print(f"refused: {exc}", file=sys.stderr)
                return 1
            print(json.dumps(out, indent=2, default=str))
            return 0
        if args.incidents_command == "reject":
            inc.reject(conn, args.incident_id, args.action, actor=args.actor, note=args.note)
            print("recorded")
            return 0
        if args.incidents_command == "outcome":
            inc.record_outcome(conn, args.incident_id, actor=args.actor, outcome=args.note,
                               close=args.close)
            print("recorded")
            return 0
    return 2


def register(sub: argparse._SubParsersAction) -> None:
    from src.compliance.cli import register as register_compliance

    register_compliance(sub)
    ops = sub.add_parser("ops", help="Operations layer: turns, capacity, readiness, incidents")
    ops_sub = ops.add_subparsers(dest="ops_command", required=True)

    s = ops_sub.add_parser("sources", help="Status of every operations data source")
    s.set_defaults(func=cmd_ops_sources)

    s = ops_sub.add_parser("profiles", help="Show and store property turnover profiles")
    s.set_defaults(func=cmd_ops_profiles)

    s = ops_sub.add_parser("import", help="Import outcomes/capacity/events from a source")
    s.add_argument("--source", required=True,
                   choices=["csv", "guesty_tasks", "breezeway", "turno", "telemetry", "manual", "webhooks"])
    s.add_argument("--file")
    s.add_argument("--kind", default="outcomes",
                   choices=["outcomes", "capacity", "asset_events", "ledger", "credentials"])
    s.add_argument("--preset", default="generic",
                   choices=["generic", "turno", "breezeway_export", "guesty_tasks_export"])
    s.add_argument("--from", dest="start")
    s.add_argument("--to", dest="end")
    s.add_argument("--as-of", dest="as_of")
    s.set_defaults(func=cmd_ops_import)

    s = ops_sub.add_parser("report", help="Shadow operations report (writes nothing)")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--as-of", dest="as_of")
    s.add_argument("--property")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_ops_report)

    s = ops_sub.add_parser("capacity", help="Crew load for one service date")
    s.add_argument("--date", required=True)
    s.add_argument("--as-of", dest="as_of")
    s.set_defaults(func=cmd_ops_capacity)

    ev = ops_sub.add_parser("event", help="Asset-health events")
    ev_sub = ev.add_subparsers(dest="event_command", required=True)
    s = ev_sub.add_parser("add", help="Record an event, optionally moving readiness state")
    s.add_argument("--property", required=True)
    s.add_argument("--system", required=True,
                   choices=["heat", "water", "septic", "spa", "lock", "snow_access", "power",
                            "propane", "co_safety", "fireplace", "wildfire", "other"])
    s.add_argument("--severity", default="warn", choices=["info", "warn", "critical"])
    s.add_argument("--source-type", default="manual",
                   choices=["sensor", "guest", "cleaner", "vendor", "manual"])
    s.add_argument("--ref")
    s.add_argument("--reading", help="JSON object of readings")
    s.add_argument("--observed-at")
    s.add_argument("--effective-from")
    s.add_argument("--effective-to")
    s.add_argument("--verified-by")
    s.add_argument("--state", choices=["ready", "at_risk", "inspection_required", "out_of_service",
                                       "remediation_in_progress", "verified_ready"])
    s.add_argument("--actor", default="operator")
    s.add_argument("--note")
    s.set_defaults(func=cmd_ops_event_add)

    s = ops_sub.add_parser("readiness", help="Readiness state and revenue at risk per property")
    s.add_argument("--as-of", dest="as_of")
    s.add_argument("--scan-signals", action="store_true",
                   help="Let threshold signals move ready properties to at_risk")
    s.set_defaults(func=cmd_ops_readiness)

    inc = ops_sub.add_parser("incidents", help="Signal-driven incident candidates")
    inc_sub = inc.add_subparsers(dest="incidents_command", required=True)
    s = inc_sub.add_parser("scan")
    s.add_argument("--as-of", dest="as_of")
    s.set_defaults(func=cmd_ops_incidents)
    s = inc_sub.add_parser("list")
    s.add_argument("--status")
    s.set_defaults(func=cmd_ops_incidents)
    s = inc_sub.add_parser("show")
    s.add_argument("incident_id")
    s.set_defaults(func=cmd_ops_incidents)
    s = inc_sub.add_parser("approve")
    s.add_argument("incident_id")
    s.add_argument("--action", required=True)
    s.add_argument("--actor", required=True)
    s.add_argument("--adapter", default="dry_run", choices=["dry_run", "guesty", "breezeway"])
    s.add_argument("--confirm-live-write", action="store_true")
    s.set_defaults(func=cmd_ops_incidents)
    s = inc_sub.add_parser("reject")
    s.add_argument("incident_id")
    s.add_argument("--action", required=True)
    s.add_argument("--actor", required=True)
    s.add_argument("--note")
    s.set_defaults(func=cmd_ops_incidents)
    s = inc_sub.add_parser("outcome")
    s.add_argument("incident_id")
    s.add_argument("--actor", required=True)
    s.add_argument("--note", required=True)
    s.add_argument("--close", action="store_true")
    s.set_defaults(func=cmd_ops_incidents)
