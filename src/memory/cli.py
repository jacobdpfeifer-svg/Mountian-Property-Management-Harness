"""CLI handlers for wp-price memory. No rate writes."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.memory.claims import (
    ClaimError,
    confirm_claim,
    propose_claim,
    reject_claim,
    revoke_claim,
    supersede_claim,
)
from src.memory.db import connect_memory
from src.memory.intake import (
    backup_database,
    delete_file,
    export_file,
    ingest_inbox,
    status_counts,
)
from src.memory.paths import ensure_layout


def _conn(root: Path):
    return connect_memory(root)


def cmd_memory_status(_args: argparse.Namespace) -> int:
    root = ensure_layout()
    conn = _conn(root)
    try:
        counts = status_counts(conn)
    finally:
        conn.close()
    print(f"Memory root: {root}")
    print(
        "Files stored {files_stored}; quarantined {files_quarantined}; "
        "claims proposed {claims_proposed}; active {claims_active}; "
        "conflicted {claims_conflicted}".format(**counts)
    )
    print("Backup with `wp-price memory backup --dest <path>` (SQLite online backup).")
    return 0


def cmd_memory_ingest(_args: argparse.Namespace) -> int:
    results = ingest_inbox()
    if not results:
        print("Inbox empty.")
        return 0
    for result in results:
        print(f"{result.code} file={result.file_id or '-'} claim={result.claim_id or '-'}")
    return 0


def cmd_memory_propose(args: argparse.Namespace) -> int:
    fields = {
        "kind": args.kind,
        "property_id": args.property,
        "scope_type": args.scope,
        "stay_from": args.start,
        "stay_to": args.end,
        "review_after": args.review_after or args.end,
        "minimum": args.minimum,
        "note": args.note,
    }
    root = ensure_layout()
    conn = _conn(root)
    try:
        proposed = propose_claim(conn, fields, file_id=args.file_id, actor="operator")
        conn.commit()
    except ClaimError as exc:
        print(exc.code)
        return 2
    finally:
        conn.close()
    print(f"proposed {proposed.claim_id}")
    return 0


def _mutate(args: argparse.Namespace, fn) -> int:
    root = ensure_layout()
    conn = _conn(root)
    try:
        status = fn(conn, args.claim_id)
        conn.commit()
    except ClaimError as exc:
        print(exc.code)
        return 2
    finally:
        conn.close()
    print(f"{args.claim_id} {status}")
    return 0


def cmd_memory_confirm(args: argparse.Namespace) -> int:
    return _mutate(args, confirm_claim)


def cmd_memory_reject(args: argparse.Namespace) -> int:
    return _mutate(args, reject_claim)


def cmd_memory_revoke(args: argparse.Namespace) -> int:
    return _mutate(args, revoke_claim)


def cmd_memory_supersede(args: argparse.Namespace) -> int:
    root = ensure_layout()
    conn = _conn(root)
    try:
        status = supersede_claim(conn, args.claim_id, args.replaces)
        conn.commit()
    except ClaimError as exc:
        print(exc.code)
        return 2
    finally:
        conn.close()
    print(f"{args.claim_id} {status}")
    return 0


def cmd_memory_delete(args: argparse.Namespace) -> int:
    root = ensure_layout()
    conn = _conn(root)
    try:
        status = delete_file(conn, args.file_id, root=root)
        conn.commit()
    finally:
        conn.close()
    print(status)
    return 0 if status == "deleted" else 2


def cmd_memory_export(args: argparse.Namespace) -> int:
    root = ensure_layout()
    conn = _conn(root)
    try:
        dest = export_file(conn, args.file_id, Path(args.dest), root=root)
    except (ValueError, OSError) as exc:
        print(type(exc).__name__)
        return 2
    finally:
        conn.close()
    print(dest)
    return 0


def cmd_memory_backup(args: argparse.Namespace) -> int:
    dest = backup_database(Path(args.dest))
    print(dest)
    return 0


def cmd_receipt(args: argparse.Namespace) -> int:
    from src.receipt.render import write_receipt

    try:
        path = write_receipt(args.db, args.run_id, output=Path(args.output) if args.output else None)
    except LookupError:
        print(f"No run {args.run_id}")
        return 2
    print(path)
    return 0
