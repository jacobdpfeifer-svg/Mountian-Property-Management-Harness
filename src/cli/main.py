"""CLI entrypoint: wp-price."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from src.compose import generate_recommendations
from src.config import load_policy
from src.db import DEFAULT_DB_PATH, connect, init_db, resolve_property_ids
from src.eval import format_report, portfolio_reports, record_outcomes_from_inventory
from src.explain.present import format_owner_recommendation
from src.guardrails import assess_data_health, limit_run_scope
from src.ingest import CsvIngestAdapter, ICalIngestAdapter
from src.pacing import backfill_from_inventory, take_snapshot, verify_snapshots
from src.pms import ADAPTERS, push_recommendations
from src.scrape import discover_comps, run_scrape
from src.scrape.properties import discover_owned_listings, persist_room_ids, scrape_properties
from src.scrape.providers import PROVIDERS, FixtureProvider, PyAirbnbProvider
from src.utils import parse_date

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample"
SCRAPE = ROOT / "data" / "scrape"


def cmd_init_db(args: argparse.Namespace) -> int:
    path = init_db(args.db)
    print(f"Initialized schema at {path}")
    return 0


def cmd_seed_scrape(args: argparse.Namespace) -> int:
    """Load scrape-native portfolio CSVs (Summit Haus + Overlook Ridge, no Guesty)."""
    init_db(args.db)
    adapter = CsvIngestAdapter(
        properties_csv=SCRAPE / "properties.csv",
        inventory_csv=SCRAPE / "inventory.csv",
        comps_csv=SCRAPE / "comps.csv",
    )
    with connect(args.db) as conn:
        counts = adapter.load_all(conn)
    print(f"Seeded scrape portfolio: {counts}")
    return 0


def cmd_discover_properties(args: argparse.Namespace) -> int:
    policy = load_policy()
    provider = _make_provider(args, policy)
    window = int(policy["scrape"]["window_nights"])
    dates = [parse_date(d) for d in args.date.split(",")]
    matches = discover_owned_listings(
        provider, dates, nights=window, min_price=args.min_price,
        property_ids=args.property.split(",") if args.property else None,
    )
    if not matches:
        print("No owned listings matched — try different dates or lower --min-price.")
        return 1
    print(f"{'property_id':16}{'room_id':22}{'score':>6}  name")
    for m in matches:
        print(f"{m.property_id:16}{m.room_id:22}{m.score:>6}  {(m.name or '')[:48]}")
    if args.persist:
        with connect(args.db) as conn:
            persist_room_ids(conn, matches)
        print(f"\nPersisted {len(matches)} room id(s) to properties.airbnb_room_id")
    return 0


def cmd_scrape_properties(args: argparse.Namespace) -> int:
    policy = load_policy()
    provider = _make_provider(args, policy)
    start = parse_date(args.start)
    end = parse_date(args.end)
    with connect(args.db) as conn:
        rep = scrape_properties(
            conn, provider, start, end, policy=policy,
            discover=args.discover,
            discover_dates=[parse_date(d) for d in args.discover_date.split(",")]
            if args.discover_date else None,
        )
    if rep.discovery:
        print("Discovery:")
        for m in rep.discovery:
            print(f"  {m.property_id}: {m.room_id} ({m.name}) score={m.score}")
    print(f"Sweeps: {rep.sweeps_ok} ok, {rep.sweeps_failed} failed")
    for p in rep.properties:
        print(
            f"  {p.property_id}: {p.nights_written} nights "
            f"({p.nights_with_price} priced, {p.nights_available} avail, "
            f"{p.nights_booked} booked)"
        )
        for e in p.errors:
            print(f"    WARNING: {e}")
    return 0 if rep.properties else 1


def _resolve_scope(conn, args: argparse.Namespace) -> list[str] | None:
    props = None
    raw = getattr(args, "property", None)
    if raw:
        props = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        return resolve_property_ids(
            conn,
            property_ids=props,
            owner_id=getattr(args, "owner", None),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def cmd_export(args: argparse.Namespace) -> int:
    from src.eval.export import export_recommendations_csv

    start = parse_date(args.start)
    end = parse_date(args.end)
    out = Path(args.output)
    with connect(args.db) as conn:
        props = _resolve_scope(conn, args)
        n = export_recommendations_csv(conn, start, end, out, property_ids=props)
    print(f"Exported {n} rows to {out}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    from src.audit import format_audit, run_audit

    start = parse_date(args.start)
    end = parse_date(args.end)
    policy = load_policy()
    with connect(args.db) as conn:
        props = _resolve_scope(conn, args)
        report = run_audit(conn, start, end, property_ids=props, policy=policy)
    text = format_audit(report)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote {args.output}")
    return 0 if report.passed else 1


def cmd_seed_sample(args: argparse.Namespace) -> int:
    init_db(args.db)
    adapter = CsvIngestAdapter(
        properties_csv=SAMPLE / "properties.csv",
        inventory_csv=SAMPLE / "nightly_inventory.csv",
        comps_csv=SAMPLE / "comps.csv",
        demand_csv=SAMPLE / "demand_signals.csv",
        inquiries_csv=SAMPLE / "booking_inquiries.csv",
    )
    with connect(args.db) as conn:
        counts = adapter.load_all(conn)
    print(f"Seeded sample data: {counts}")
    ical = SAMPLE / "cabin_ridge.ics"
    if ical.exists():
        with connect(args.db) as conn:
            n = ICalIngestAdapter("cabin_ridge", ical, default_listed_price=650).load_inventory(conn)
        print(f"Merged iCal nights for cabin_ridge: {n}")
    return 0


def cmd_ingest_csv(args: argparse.Namespace) -> int:
    if not any([args.properties, args.inventory, args.comps, args.demand, args.inquiries]):
        print("Need at least one of --properties, --inventory, --comps, --demand, --inquiries",
              file=sys.stderr)
        return 1
    init_db(args.db)
    adapter = CsvIngestAdapter(
        properties_csv=args.properties,
        inventory_csv=args.inventory,
        comps_csv=args.comps,
        demand_csv=args.demand,
        inquiries_csv=args.inquiries,
    )
    with connect(args.db) as conn:
        counts = adapter.load_all(conn)
    print(json.dumps(counts, indent=2))
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Daily pacing capture. Every day this does not run is unrecoverable."""
    with connect(args.db) as conn:
        if args.verify:
            since = parse_date(args.since) if args.since else None
            report = verify_snapshots(conn, since=since)
            print(json.dumps(report, indent=2))
            if report["status"] != "ok":
                print("  Pacing coverage will stay degraded until every (property, as_of) "
                      "day since first Guesty sync is present — skipped days are unrecoverable.")
            return 0 if report["status"] == "ok" else 1
        if args.backfill:
            print(json.dumps(backfill_from_inventory(conn, days=args.backfill), indent=2))
        result = take_snapshot(conn)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "ok" else 1


def _make_provider(args: argparse.Namespace, policy: dict):
    if args.provider == "fixture":
        return FixtureProvider(args.fixture)
    cfg = policy.get("scrape", {})
    return PyAirbnbProvider(cfg.get("bbox", {}), policy,
                            proxy_url=args.proxy or cfg.get("proxy_url", ""))


def cmd_sync_guesty(args: argparse.Namespace) -> int:
    """Pull listings, calendar and reservations from Guesty into the local schema."""
    from src.pms.guesty import GuestyClient
    from src.pms.sync import sync_all

    init_db(args.db)
    client = GuestyClient()
    with connect(args.db) as conn:
        rep = sync_all(conn, client, horizon_days=args.horizon, history_days=args.history)
    print(f"Synced {rep.listings} listing(s) from Guesty")
    print(f"  Calendar nights:        {rep.nights}")
    print(f"  Calendar span:          {rep.calendar_min} → {rep.calendar_max}")
    print(f"  Reservations:           {rep.reservations}")
    print(f"  Reservation check-ins:  {rep.reservation_checkin_min} → {rep.reservation_checkin_max}")
    print(f"  With confirmedAt:       {rep.reservations_with_confirmed_at}")
    print(f"  Booked nights w/ price: {rep.booked_nights_priced}")
    for w in rep.warnings:
        print(f"  WARNING: {w}")
    return 0


def cmd_backtest_guesty(args: argparse.Namespace) -> int:
    """Ceiling/comp/leakage retrospective vs Guesty realised prices. Not a pacing proof."""
    from src.eval.retrospective import (
        format_markdown,
        score_history,
        seed_curated_comps,
        write_report,
    )

    init_db(args.db)
    start = parse_date(args.start) if args.start else None
    end = parse_date(args.end) if args.end else None
    policy = load_policy()
    with connect(args.db) as conn:
        comps = seed_curated_comps(conn)
        print(f"Curated comps loaded: {comps}")
        props = _resolve_scope(conn, args)
        report = score_history(
            conn,
            start=start,
            end=end,
            property_ids=props,
            policy=policy,
            lead_days=int(args.lead_days),
        )
    text = format_markdown(report)
    if args.output:
        path = write_report(report, args.output)
        print(f"Wrote {path}")
    print(text)
    return 0


def cmd_scrape_comps(args: argparse.Namespace) -> int:
    policy = load_policy()
    horizon = args.horizon or int(policy.get("scrape", {}).get("horizon_days", 120))
    provider = _make_provider(args, policy)
    with connect(args.db) as conn:
        rep = run_scrape(conn, provider, policy, horizon_days=horizon,
                         start=parse_date(args.start) if args.start else None,
                         fetch_calendars=not args.no_calendars)
    icon = {"ok": "OK", "degraded": "DEGRADED", "failed": "FAILED"}.get(rep.status, rep.status)
    print(f"Scrape {rep.run_id} via '{rep.provider}': {icon}")
    print(f"  Windows:      {rep.windows_ok}/{rep.windows_attempted} passed validation")
    print(f"  Listings seen: {rep.listings_seen}")
    print(f"  Comps matched: {rep.comps_matched}/{rep.comps_expected} "
          f"({rep.comp_match_rate:.0%})")
    print(f"  Observations:  {rep.observations} written, {rep.rejected} rejected")
    if rep.errors:
        print(f"  Errors ({len(rep.errors)}):")
        for e in rep.errors[:8]:
            print(f"    - {e}")
        if len(rep.errors) > 8:
            print(f"    ... {len(rep.errors) - 8} more (see comp_scrape_runs.errors)")
    if rep.status != "ok":
        print("  Comp coverage will be gated by src/guardrails; autonomy stays advisory.")
    return 0 if rep.status == "ok" else 1


def cmd_discover_comps(args: argparse.Namespace) -> int:
    policy = load_policy()
    cfg = policy.get("scrape", {}).get("discover", {})
    provider = _make_provider(args, policy)
    check_in = parse_date(args.date) if args.date else date.today() + timedelta(days=45)
    gcfg = policy.get("scrape", {}).get("group_size", {})
    min_bedrooms = args.min_bedrooms if args.min_bedrooms is not None else None
    min_sleeps = args.min_sleeps if args.min_sleeps is not None else None
    rows = discover_comps(
        provider,
        check_in,
        int(policy["scrape"]["window_nights"]),
        min_price=args.min_price or float(cfg.get("min_price", 400)),
        limit=args.limit or int(cfg.get("limit", 40)),
        min_bedrooms=min_bedrooms,
        min_sleeps=min_sleeps,
        policy=policy,
    )
    if not rows:
        print("No listings returned — the sweep failed or nothing cleared the price/size floor.")
        return 1
    bd_floor = min_bedrooms if min_bedrooms is not None else gcfg.get("min_bedrooms", "?")
    sl_floor = min_sleeps if min_sleeps is not None else gcfg.get("min_sleeps", "?")
    print(f"Top {len(rows)} Winter Park / Fraser listings by nightly rate for {check_in} "
          f"(group-size filter: bd>={bd_floor}, sleeps>={sl_floor}):\n")
    print(f"{'room_id':22}{'$/night':>9}{'bd':>4}{'slp':>5}  name")
    for r in rows:
        bd = "" if r.get("bedrooms") is None else str(r["bedrooms"])
        sl = "" if r.get("sleeps") is None else str(r["sleeps"])
        print(f"{r['room_id']:22}{r['nightly_price']:>9.0f}{bd:>4}{sl:>5}  {(r['name'] or '')[:48]}")
    print("\nReview against docs/CLOUD9_COMP_BRIEF.md (score ≥70, substitutable).")
    print("Add keepers to data/cloud9/comps.csv (for_properties=cloud_9) or data/scrape/comps.csv,")
    print("then `wp-price ingest-csv --comps <file>` so scrape-comps can refresh them.")
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    policy = load_policy()
    with connect(args.db) as conn:
        props = _resolve_scope(conn, args)
        h = assess_data_health(conn, policy, property_ids=props)
    print(f"Granted autonomy level: {h.granted_level.upper()}")
    print(f"  PMS data age:   {h.pms_age_hours:.1f}h" if h.pms_age_hours is not None else "  PMS data age:   unknown")
    print(f"  Comp data age:  {h.comp_age_hours:.1f}h" if h.comp_age_hours is not None else "  Comp data age:  none")
    print(f"  Comp coverage:  {h.comp_coverage:.0%}")
    print(f"  Pacing history: {h.pacing_days} day(s)")
    if h.failures:
        label = "Gate failures (grace period active):" if h.grace_active else "Gate failures (autonomy demoted to SUGGEST):"
        print(f"  {label}")
        for f in h.failures:
            print(f"    - {f}")
    else:
        print("  All gates passed.")
    return 0


def _print_recs(recs, limit: int, *, technical: bool = False) -> None:
    for rec in recs[:limit]:
        print(format_owner_recommendation(rec, technical=technical))
    if len(recs) > limit:
        print(f"  ... {len(recs) - limit} more")


def cmd_recommend(args: argparse.Namespace) -> int:
    start = parse_date(args.start)
    end = parse_date(args.end)
    policy = load_policy()
    with connect(args.db) as conn:
        props = _resolve_scope(conn, args)
        recs, health = generate_recommendations(
            conn, start, end, property_ids=props, policy=policy,
            persist=not args.dry_run, allow_past=args.allow_past,
        )
    blocked = sum(1 for r in recs if r.status == "blocked")
    clamped = sum(1 for r in recs if r.guardrail_action
                  and r.guardrail_action.startswith("clamped"))
    print(f"Generated {len(recs)} recommendations ({policy.get('rule_version')} / "
          f"{policy.get('model_version')})")
    print(f"Autonomy granted: {health.granted_level.upper()}"
          + (f"  [{len(health.failures)} gate failure(s) — run `wp-price health`]" if health.failures else ""))
    print(f"Guardrails: {clamped} clamped, {blocked} blocked/escalated")
    _print_recs(recs, args.limit, technical=args.technical)
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    """Auto-push within guardrails. Refuses unless the health gate grants 'handle'."""
    start = parse_date(args.start)
    end = parse_date(args.end)
    policy = load_policy()
    with connect(args.db) as conn:
        props = _resolve_scope(conn, args)
        adapter = (ADAPTERS[args.adapter](conn) if args.adapter == "guesty"
                   else ADAPTERS[args.adapter]())
        recs, health = generate_recommendations(
            conn, start, end, property_ids=props, policy=policy, persist=True
        )
        open_sql = (
            "SELECT COUNT(*) AS c FROM nightly_inventory WHERE status='available' "
            "AND stay_date >= ? AND stay_date <= ?"
        )
        open_params: list[object] = [start.isoformat(), end.isoformat()]
        if props:
            placeholders = ",".join("?" for _ in props)
            open_sql += f" AND property_id IN ({placeholders})"
            open_params.extend(props)
        open_nights = conn.execute(open_sql, open_params).fetchone()["c"]
        pushable, withheld = limit_run_scope(recs, int(open_nights or 0), policy)
        print(f"Autonomy granted: {health.granted_level.upper()}")
        for f in health.failures:
            print(f"  gate: {f}")
        if withheld:
            print(f"Run scope cap: withholding {len(withheld)} largest move(s) for review")
        counts = push_recommendations(conn, pushable, adapter, health.granted_level, policy=policy)
    print(f"Push via '{args.adapter}': {json.dumps(counts)}")
    if health.granted_level != "handle":
        print("No rates written — data health did not grant 'handle'. "
              "Recommendations are queued as suggestions.")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    start = parse_date(args.start)
    end = parse_date(args.end)
    with connect(args.db) as conn:
        props = _resolve_scope(conn, args)
        n = record_outcomes_from_inventory(conn, start, end)
        print(f"Recorded/updated {n} recommendation outcomes")
        reports = portfolio_reports(
            conn, start, end, property_ids=props, owner_id=getattr(args, "owner", None)
        )
    for report in reports:
        print(format_report(report))
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wp-price", description="Winter Park STR Pricing Engine")
    p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite DB path")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init-db", help="Create / migrate schema")
    s.set_defaults(func=cmd_init_db)

    s = sub.add_parser("seed-scrape", help="Load scrape-native portfolio (Summit/Overlook)")
    s.set_defaults(func=cmd_seed_scrape)

    s = sub.add_parser("seed-sample", help="Load data/sample CSVs (+ optional iCal)")
    s.set_defaults(func=cmd_seed_sample)

    s = sub.add_parser("ingest-csv", help="Ingest operator CSV exports")
    s.add_argument("--properties")
    s.add_argument("--inventory")
    s.add_argument("--comps")
    s.add_argument("--demand")
    s.add_argument("--inquiries")
    s.set_defaults(func=cmd_ingest_csv)

    s = sub.add_parser("snapshot", help="Daily pacing capture (run before ingest)")
    s.add_argument("--backfill", type=int, default=0, help="Bootstrap N prior days (biased)")
    s.add_argument("--verify", action="store_true",
                   help="Check pacing_snapshots for missing (property_id, as_of) days; "
                        "exit 1 if degraded or failed")
    s.add_argument("--since", help="Verify window start (default: earliest Guesty sync date)")
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("sync-guesty", help="Pull listings/calendar/reservations from Guesty")
    s.add_argument("--horizon", type=int, default=365, help="Days forward to pull")
    s.add_argument("--history", type=int, default=730, help="Days back to pull")
    s.set_defaults(func=cmd_sync_guesty)

    s = sub.add_parser(
        "backtest-guesty",
        help="Honest retrospective vs Guesty realised prices (ceiling/leakage; not pacing)",
    )
    s.add_argument("--from", dest="start", help="First stay date (default: earliest inventory)")
    s.add_argument("--to", dest="end", help="Last stay date (default: yesterday)")
    s.add_argument("--property", help="Comma-separated property_id filter")
    s.add_argument("--owner", help="Owner id filter (properties.owner_id)")
    s.add_argument("--lead-days", type=int, default=30, help="Decision date = stay minus this")
    s.add_argument("--output", "-o", default="docs/reports/GUESTY_RETROSPECTIVE.md")
    s.set_defaults(func=cmd_backtest_guesty)

    s = sub.add_parser("health", help="Show data health and the autonomy level it grants")
    s.add_argument("--owner", help="Owner id filter (properties.owner_id)")
    s.add_argument("--property", help="Comma-separated property_id filter")
    s.set_defaults(func=cmd_health)

    def _scrape_args(sp):
        sp.add_argument("--provider", default="airbnb_sweep", choices=sorted(PROVIDERS))
        sp.add_argument("--fixture", help="Fixture JSON path (--provider fixture)")
        sp.add_argument("--proxy", default="", help="Proxy URL for the sweep")
        return sp

    s = _scrape_args(sub.add_parser("scrape-comps", help="Sweep the market and refresh comp prices"))
    s.add_argument("--horizon", type=int, help="Days forward to sample (default from policy)")
    s.add_argument("--start", help="First check-in date to sample (default: today)")
    s.add_argument("--no-calendars", action="store_true",
                   help="Skip the per-comp calendar pass (faster, no min-stay data)")
    s.set_defaults(func=cmd_scrape_comps)

    s = _scrape_args(sub.add_parser("discover-comps", help="Rank the live market to curate a comp set"))
    s.add_argument("--date", help="Check-in date to price (default: today + 45d)")
    s.add_argument("--min-price", type=float)
    s.add_argument("--limit", type=int)
    s.add_argument("--min-bedrooms", type=int,
                   help="Override scrape.group_size.min_bedrooms for this sweep")
    s.add_argument("--min-sleeps", type=int,
                   help="Override scrape.group_size.min_sleeps (Cloud 9 brief: 16)")
    s.set_defaults(func=cmd_discover_comps)

    s = _scrape_args(sub.add_parser("discover-properties", help="Find owned listings in market sweeps"))
    s.add_argument("--date", required=True, help="Comma-separated check-in dates")
    s.add_argument("--min-price", type=float, default=300)
    s.add_argument("--property", help="Comma-separated property_id filter")
    s.add_argument("--persist", action="store_true", help="Write room ids to DB")
    s.set_defaults(func=cmd_discover_properties)

    s = _scrape_args(sub.add_parser("scrape-properties", help="Scrape owned listing inventory"))
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--discover", action="store_true", help="Discover room ids before scrape")
    s.add_argument("--discover-date", help="Comma-separated dates for discovery sweeps")
    s.set_defaults(func=cmd_scrape_properties)

    s = sub.add_parser("export", help="Export recommendations to CSV")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--property", help="Comma-separated property_id filter")
    s.add_argument("--owner", help="Owner id filter (properties.owner_id)")
    s.add_argument("--output", "-o", default="data/exports/recommendations.csv")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("audit", help="Post-run audit checklist")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--property", help="Comma-separated property_id filter")
    s.add_argument("--owner", help="Owner id filter (properties.owner_id)")
    s.add_argument("--output", "-o", help="Write markdown report to file")
    s.set_defaults(func=cmd_audit)

    s = sub.add_parser("push", help="Generate and auto-push rates within guardrails")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--property")
    s.add_argument("--owner", help="Owner id filter (properties.owner_id)")
    s.add_argument("--adapter", default="dry_run", choices=sorted(ADAPTERS))
    s.set_defaults(func=cmd_push)

    s = sub.add_parser("recommend", help="Generate explainable nightly recommendations")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--property", help="Comma-separated property_id filter")
    s.add_argument("--owner", help="Owner id filter (properties.owner_id)")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--allow-past", action="store_true",
                   help="Price nights in the past (backtesting only)")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument(
        "--technical",
        action="store_true",
        help="Show internal reason strings (beta, sample counts) instead of owner language",
    )
    s.set_defaults(func=cmd_recommend)

    s = sub.add_parser("report", help="Offline RevPAN report + outcomes join")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--property", help="Comma-separated property_id filter")
    s.add_argument("--owner", help="Owner id filter (properties.owner_id)")
    s.set_defaults(func=cmd_report)

    # --- Pfeifer Optimization -------------------------------------------------
    sig = sub.add_parser("signals", help="Pfeifer Optimization collectors / store")
    sig_sub = sig.add_subparsers(dest="signals_command", required=True)

    s = sig_sub.add_parser("run", help="Run a collector for a market")
    s.add_argument("--collector", required=True)
    s.add_argument("--market", default="grand_home")
    s.add_argument("--as-of", dest="as_of", default=None)
    s.add_argument("--fixture", default=None, help="Optional fixture path for offline runs")
    s.set_defaults(func=cmd_signals_run)

    s = sig_sub.add_parser("status", help="Recent signal runs")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_signals_status)

    s = sig_sub.add_parser("list", help="List registered collectors / definitions")
    s.set_defaults(func=cmd_signals_list)

    s = sig_sub.add_parser("scoreboard", help="Latest signal scores + ladder status")
    s.set_defaults(func=cmd_signals_scoreboard)

    s = sig_sub.add_parser("cycle", help="Run the daily collector cycle")
    s.add_argument("--as-of", dest="as_of", default=None)
    s.set_defaults(func=cmd_signals_cycle)

    s = sig_sub.add_parser("brief", help="Weekly analyst brief (prose only)")
    s.add_argument("--as-of", dest="as_of", default=None)
    s.set_defaults(func=cmd_signals_brief)

    s = sig_sub.add_parser("resort-brief", help="Winter Park resort ops brief")
    s.add_argument("--as-of", dest="as_of", default=None)
    s.add_argument("--market", default="grand_home")
    s.set_defaults(func=cmd_signals_resort_brief)

    s = sig_sub.add_parser("rescore", help="Rescore all ladder signals against outcomes")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--horizon-days", type=int, default=14)
    s.set_defaults(func=cmd_signals_rescore)

    s = sig_sub.add_parser("promote", help="Apply promotion ladder from latest scores")
    s.set_defaults(func=cmd_signals_promote)

    return p


def cmd_signals_run(args: argparse.Namespace) -> int:
    import src.signals.collectors  # noqa: F401
    from src.signals.collector import get_collector
    from src.signals.store import SignalStore

    init_db(args.db)
    as_of = parse_date(args.as_of) if args.as_of else date.today()
    with connect(args.db) as conn:
        store = SignalStore(conn)
        store.seed_markets()
        from src.signals.promotion import register_ladder_signals

        register_ladder_signals(store)
        cls = get_collector(args.collector)
        kwargs = {}
        if args.fixture:
            kwargs["fixture_path"] = Path(args.fixture)
        result = cls(store, **kwargs).run(as_of, args.market)
    print(json.dumps({
        "run_id": result.run_id,
        "status": result.status,
        "written": result.written,
        "rejected": result.rejected,
        "errors": result.errors[:10],
    }, indent=2))
    return 0 if result.status != "failed" else 1


def cmd_signals_status(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        rows = conn.execute(
            "SELECT run_id, collector, market_id, as_of, status, observations, rejected "
            "FROM signal_runs ORDER BY started_at DESC LIMIT ?",
            (args.limit,),
        ).fetchall()
    for r in rows:
        print(
            f"{r['run_id']}  {r['collector']:12}  {r['market_id'] or '-':18}  "
            f"{r['as_of']}  {r['status']:8}  ok={r['observations']}  rej={r['rejected']}"
        )
    return 0


def cmd_signals_list(args: argparse.Namespace) -> int:
    import src.signals.collectors  # noqa: F401
    from src.signals.collector import list_collectors
    from src.signals.store import SignalStore

    init_db(args.db)
    print("Collectors:", ", ".join(list_collectors()))
    with connect(args.db) as conn:
        store = SignalStore(conn)
        from src.signals.promotion import register_ladder_signals

        register_ladder_signals(store)
        for d in store.list_definitions():
            print(f"  {d['signal_key']:40} {d['status']:12} {d['source']}")
    return 0


def cmd_signals_scoreboard(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        rows = conn.execute(
            """
            SELECT d.signal_key, d.status, s.sample_size, s.information_coefficient,
                   s.ic_ci_low, s.ic_ci_high, s.hit_rate, s.decision, s.scored_at
            FROM signal_definitions d
            LEFT JOIN signal_scores s ON s.signal_key = d.signal_key
            ORDER BY d.signal_key, s.scored_at DESC
            """
        ).fetchall()
    seen = set()
    print("f(SQI) is a declared prior — SQI is architecture, not on this ladder.")
    for r in rows:
        if r["signal_key"] in seen:
            continue
        seen.add(r["signal_key"])
        ic = r["information_coefficient"]
        print(
            f"{r['signal_key']:40} {r['status']:12} "
            f"n={r['sample_size'] or '-'}  ic={ic if ic is not None else '-'}  "
            f"decision={r['decision'] or '-'}"
        )
    return 0


def cmd_signals_cycle(args: argparse.Namespace) -> int:
    from src.signals.orchestrator import run_daily_cycle
    from src.signals.store import SignalStore

    init_db(args.db)
    as_of = parse_date(args.as_of) if args.as_of else date.today()
    with connect(args.db) as conn:
        store = SignalStore(conn)
        store.seed_markets()
        from src.signals.promotion import register_ladder_signals

        register_ladder_signals(store)
        report = run_daily_cycle(store, as_of)
    print(json.dumps(report, indent=2, default=str))
    return 0 if not report.get("failures") else 1


def cmd_signals_brief(args: argparse.Namespace) -> int:
    from src.signals.analyst import weekly_brief
    from src.signals.store import SignalStore

    init_db(args.db)
    as_of = parse_date(args.as_of) if args.as_of else date.today()
    with connect(args.db) as conn:
        print(weekly_brief(SignalStore(conn), as_of))
    return 0


def cmd_signals_resort_brief(args: argparse.Namespace) -> int:
    from src.signals.analyst import resort_brief
    from src.signals.store import SignalStore

    init_db(args.db)
    as_of = parse_date(args.as_of) if args.as_of else date.today()
    with connect(args.db) as conn:
        print(resort_brief(SignalStore(conn), as_of, market_id=args.market))
    return 0


def cmd_signals_rescore(args: argparse.Namespace) -> int:
    from datetime import timedelta
    from src.signals.promotion import register_ladder_signals, rescore_all
    from src.signals.store import SignalStore

    init_db(args.db)
    start = parse_date(args.start)
    end = parse_date(args.end)
    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += timedelta(days=1)
    with connect(args.db) as conn:
        store = SignalStore(conn)
        register_ladder_signals(store)
        results = rescore_all(
            store, conn, dates, horizon_days=int(args.horizon_days)
        )
    print(json.dumps(results, indent=2, default=str))
    return 0


def cmd_signals_promote(args: argparse.Namespace) -> int:
    from src.signals.promotion import apply_promotions, register_ladder_signals
    from src.signals.store import SignalStore

    init_db(args.db)
    with connect(args.db) as conn:
        store = SignalStore(conn)
        register_ladder_signals(store)
        actions = apply_promotions(store)
    for a in actions:
        print(a)
    if not actions:
        print("No promotion actions.")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
