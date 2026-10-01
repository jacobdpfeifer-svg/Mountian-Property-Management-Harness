"""`wp-price compliance ...` and `wp-price owner-receipt`."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from src.db import connect, connect_readonly
from src.utils import parse_date


def cmd_compliance_add(args: argparse.Namespace) -> int:
    from src.compliance import Credential, add_credential

    with connect(args.db) as conn:
        created = add_credential(conn, Credential(
            property_id=args.property, jurisdiction=args.jurisdiction,
            credential_type=args.type, identifier=args.identifier,
            issued_at=args.issued, expires_at=args.expires, evidence_ref=args.evidence,
            verification_status="verified" if args.verified_by else "unverified",
            verified_by=args.verified_by, notes=args.note,
            permitted_occupancy=args.occupancy,
        ))
    print("added" if created else "updated")
    return 0


def cmd_compliance_import(args: argparse.Namespace) -> int:
    from src.ops.sources.csv_import import import_csv

    with connect(args.db) as conn:
        result = import_csv(conn, args.file, kind="credentials")
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.status in ("ok", "partial") else 1


def cmd_compliance_check(args: argparse.Namespace) -> int:
    from src.compliance import check, render_text

    texts: dict[str, str] = {}
    for item in args.listing_text or []:
        pid, _, path = item.partition("=")
        if not path:
            print(f"--listing-text expects property_id=path, got {item!r}", file=sys.stderr)
            return 2
        texts[pid] = Path(path).expanduser().read_text(encoding="utf-8")
    as_of = parse_date(args.as_of) if args.as_of else None
    try:
        with connect_readonly(args.db) as conn:
            report = check(conn, as_of, listing_texts=texts)
    except sqlite3.OperationalError as exc:
        print(f"refused: compliance schema is not initialized ({exc}); run wp-price init-db once",
              file=sys.stderr)
        return 1
    print(json.dumps(report.as_dict(), indent=2) if args.json else render_text(report))
    return 0


def cmd_owner_receipt(args: argparse.Namespace) -> int:
    from src.receipt.owner_monthly import PlaceholderOwnerName, write_owner_receipt

    try:
        path = write_owner_receipt(args.db, args.owner, args.month,
                                   output=Path(args.output) if args.output else None,
                                   allow_placeholder_names=args.allow_placeholder_names)
    except (PlaceholderOwnerName, LookupError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    comp = sub.add_parser("compliance", help="Permit / inspection / contact register (tracking only)")
    comp_sub = comp.add_subparsers(dest="compliance_command", required=True)
    s = comp_sub.add_parser("add", help="Record one credential")
    s.add_argument("--property", required=True)
    s.add_argument("--jurisdiction", required=True)
    s.add_argument("--type", required=True, help="credential_type from the rule pack")
    s.add_argument("--identifier", required=True,
                   help="Stable permit, policy, document, or contact identifier")
    s.add_argument("--issued")
    s.add_argument("--expires")
    s.add_argument("--evidence", help="Path to the document; its sha256 is stored")
    s.add_argument("--verified-by")
    s.add_argument("--occupancy", type=int, help="Permitted occupancy on the permit")
    s.add_argument("--note")
    s.set_defaults(func=cmd_compliance_add)
    s = comp_sub.add_parser("import", help="Import credentials from CSV")
    s.add_argument("--file", required=True)
    s.set_defaults(func=cmd_compliance_import)
    s = comp_sub.add_parser("check", help="Deadlines and evidence per property")
    s.add_argument("--as-of", dest="as_of")
    s.add_argument("--listing-text", action="append",
                   help="property_id=path to listing text, to confirm the permit number is advertised")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_compliance_check)

    s = sub.add_parser("owner-receipt", help="Monthly owner receipt (net value, care, exceptions)")
    s.add_argument("--owner", required=True)
    s.add_argument("--month", required=True, help="YYYY-MM")
    s.add_argument("--output")
    s.add_argument("--allow-placeholder-names", action="store_true")
    s.set_defaults(func=cmd_owner_receipt)
