"""CLI entrypoint: wp-price."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from src.compose import generate_recommendations
from src.config import load_policy
from src.db import DEFAULT_DB_PATH, connect, init_db
from src.eval import format_report, portfolio_reports, record_outcomes_from_inventory
from src.guardrails import assess_data_health, limit_run_scope
from src.ingest import CsvIngestAdapter, ICalIngestAdapter
from src.pacing import backfill_from_inventory, take_snapshot
from src.pms import ADAPTERS, push_recommendations
from src.scrape import discover_comps, run_scrape
from src.scrape.providers import PROVIDERS, FixtureProvider, PyAirbnbProvider
from src.utils import parse_date

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample"


def cmd_init_db(args: argparse.Namespace) -> int:
    path = init_db(args.db)
    print(f"Initialized schema at {path}")
    return 0


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
        if args.backfill:
            print(json.dumps(backfill_from_inventory(conn, days=args.backfill), indent=2))
        print(json.dumps(take_snapshot(conn), indent=2))
    return 0


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
    print(f"  Reservations:           {rep.reservations}")
    print(f"  Booked nights w/ price: {rep.booked_nights_priced}")
    for w in rep.warnings:
        print(f"  WARNING: {w}")
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
    rows = discover_comps(provider, check_in, int(policy["scrape"]["window_nights"]),
                          min_price=args.min_price or float(cfg.get("min_price", 400)),
                          limit=args.limit or int(cfg.get("limit", 40)))
    if not rows:
        print("No listings returned — the sweep failed or nothing cleared the price floor.")
        return 1
    print(f"Top {len(rows)} Winter Park listings by nightly rate for {check_in} "
          f"(candidate luxury comp set):\n")
    print(f"{'room_id':22}{'$/night':>9}  name")
    for r in rows:
        print(f"{r['room_id']:22}{r['nightly_price']:>9.0f}  {(r['name'] or '')[:52]}")
    print("\nAdd the ones you want to data/sample/comps.csv (or your own comps CSV) with")
    print("columns comp_id,name,airbnb_room_id,for_properties, then run `wp-price ingest-csv`.")
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    policy = load_policy()
    with connect(args.db) as conn:
        h = assess_data_health(conn, policy)
    print(f"Granted autonomy level: {h.granted_level.upper()}")
    print(f"  PMS data age:   {h.pms_age_hours:.1f}h" if h.pms_age_hours is not None else "  PMS data age:   unknown")
    print(f"  Comp data age:  {h.comp_age_hours:.1f}h" if h.comp_age_hours is not None else "  Comp data age:  none")
    print(f"  Comp coverage:  {h.comp_coverage:.0%}")
    print(f"  Pacing history: {h.pacing_days} day(s)")
    if h.failures:
        print("  Gate failures (autonomy demoted to SUGGEST):")
        for f in h.failures:
            print(f"    - {f}")
    else:
        print("  All gates passed.")
    return 0


def _print_recs(recs, limit: int) -> None:
    for rec in recs[:limit]:
        listed = f"${rec.listed_price_at_run:.0f}" if rec.listed_price_at_run is not None else "-"
        delta = ""
        if rec.listed_price_at_run:
            pct = (rec.recommended_price - rec.listed_price_at_run) / rec.listed_price_at_run
            delta = f" ({pct:+.1%})"
        flag = f"  [{rec.status.upper()}]" if rec.status == "blocked" else ""
        print(
            f"  {rec.property_id:14} {rec.stay_date}  {listed:>7} -> "
            f"${rec.recommended_price:.0f}{delta}  "
            f"P(book)={rec.expected_book_prob:.0%}  {rec.autonomy_level}{flag}"
        )
        for r in rec.reasons:
            c = f"{r['contribution']:+.0f}" if r.get("contribution") else "  ."
            print(f"      {c:>7}  {r['message']}")
    if len(recs) > limit:
        print(f"  ... {len(recs) - limit} more")


def cmd_recommend(args: argparse.Namespace) -> int:
    start = parse_date(args.start)
    end = parse_date(args.end)
    policy = load_policy()
    props = args.property.split(",") if args.property else None
    with connect(args.db) as conn:
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
    _print_recs(recs, args.limit)
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    """Auto-push within guardrails. Refuses unless the health gate grants 'handle'."""
    start = parse_date(args.start)
    end = parse_date(args.end)
    policy = load_policy()
    props = args.property.split(",") if args.property else None
    with connect(args.db) as conn:
        adapter = (ADAPTERS[args.adapter](conn) if args.adapter == "guesty"
                   else ADAPTERS[args.adapter]())
        recs, health = generate_recommendations(
            conn, start, end, property_ids=props, policy=policy, persist=True
        )
        open_nights = conn.execute(
            "SELECT COUNT(*) AS c FROM nightly_inventory WHERE status='available' "
            "AND stay_date >= ? AND stay_date <= ?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()["c"]
        pushable, withheld = limit_run_scope(recs, int(open_nights or 0), policy)
        print(f"Autonomy granted: {health.granted_level.upper()}")
        for f in health.failures:
            print(f"  gate: {f}")
        if withheld:
            print(f"Run scope cap: withholding {len(withheld)} largest move(s) for review")
        counts = push_recommendations(conn, pushable, adapter, health.granted_level)
    print(f"Push via '{args.adapter}': {json.dumps(counts)}")
    if health.granted_level != "handle":
        print("No rates written — data health did not grant 'handle'. "
              "Recommendations are queued as suggestions.")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    start = parse_date(args.start)
    end = parse_date(args.end)
    with connect(args.db) as conn:
        n = record_outcomes_from_inventory(conn, start, end)
        print(f"Recorded/updated {n} recommendation outcomes")
        reports = portfolio_reports(conn, start, end)
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

    s = sub.add_parser("seed-sample", help="Load data/sample CSVs (+ optional iCal)")
    s.set_defaults(func=cmd_seed_sample)

    s = sub.add_parser("ingest-csv", help="Ingest operator CSV exports")
    s.add_argument("--properties", required=True)
    s.add_argument("--inventory", required=True)
    s.add_argument("--comps")
    s.add_argument("--demand")
    s.add_argument("--inquiries")
    s.set_defaults(func=cmd_ingest_csv)

    s = sub.add_parser("snapshot", help="Daily pacing capture (run before ingest)")
    s.add_argument("--backfill", type=int, default=0, help="Bootstrap N prior days (biased)")
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("sync-guesty", help="Pull listings/calendar/reservations from Guesty")
    s.add_argument("--horizon", type=int, default=365, help="Days forward to pull")
    s.add_argument("--history", type=int, default=540, help="Days back to pull")
    s.set_defaults(func=cmd_sync_guesty)

    s = sub.add_parser("health", help="Show data health and the autonomy level it grants")
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
    s.set_defaults(func=cmd_discover_comps)

    s = sub.add_parser("push", help="Generate and auto-push rates within guardrails")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--property")
    s.add_argument("--adapter", default="dry_run", choices=sorted(ADAPTERS))
    s.set_defaults(func=cmd_push)

    s = sub.add_parser("recommend", help="Generate explainable nightly recommendations")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
    s.add_argument("--property", help="Comma-separated property_id filter")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--allow-past", action="store_true",
                   help="Price nights in the past (backtesting only)")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_recommend)

    s = sub.add_parser("report", help="Offline RevPAN report + outcomes join")
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--to", dest="end", required=True)
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


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
