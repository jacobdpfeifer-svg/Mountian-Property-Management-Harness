"""Quarantine-first intake. A drop is never an approval and never a price."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.memory.claims import (
    EXTRACTOR_VERSION,
    ClaimError,
    instruction_flags,
    parse_claim_block,
    propose_claim,
)
from src.memory.db import connect_memory
from src.memory.paths import ensure_layout

MAX_BYTES = 25 * 1024 * 1024
DAILY_FILE_LIMIT = 20

_ALLOW_EXT = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
}
_ROUTE_EXT = {".csv", ".ics", ".xlsx", ".xls"}
_TEXT_COMPAT = {"text/plain", "text/markdown"}

_PII = (
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]"),
)


@dataclass(frozen=True)
class IntakeResult:
    code: str
    file_id: str | None = None
    claim_id: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith((b"PK\x03\x04", b"Rar!", b"7z\xbc\xaf\x27\x1c")):
        return "application/zip"
    if data.startswith((b"MZ", b"\x7fELF", b"\xfe\xed\xfa", b"#!")):
        return "application/x-executable"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in {b"heic", b"heix", b"hevc", b"mif1", b"msf1"}:
            return "image/heic"
        if brand in {b"M4A ", b"M4B ", b"mp42", b"isom"}:
            return "audio/mp4"
    if b"\x00" in data:
        return None
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return "text/plain"


def _mime_compatible(expected: str, sniffed: str | None) -> bool:
    if sniffed is None:
        return False
    if sniffed in {"application/zip", "application/x-executable"}:
        return False
    if expected in _TEXT_COMPAT and sniffed in _TEXT_COMPAT:
        return True
    return expected == sniffed


def _pii_hit(data: bytes, mime: str) -> bool:
    if mime not in _TEXT_COMPAT and mime != "text/plain":
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return any(pattern.search(text) for pattern in _PII)


def _malware_code(path: Path) -> str | None:
    """None means the structural scan passed and clamscan is absent or clean."""
    exe = shutil.which("clamscan")
    if exe is None:
        return None
    try:
        proc = subprocess.run(
            [exe, "--no-summary", str(path)],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "malware_scan_failed"
    if proc.returncode == 0:
        return None
    return "malware_scan_failed"


def _write(folder: Path, file_id: str, data: bytes) -> str:
    dest = folder / file_id
    dest.write_bytes(data)
    os.chmod(dest, 0o600)
    return f"{folder.name}/{file_id}"


def _insert_file(
    conn: sqlite3.Connection,
    *,
    file_id: str,
    digest: str,
    storage_key: str,
    ext: str,
    mime: str,
    size: int,
    source: str,
    status: str,
    pii_status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO memory_files (
            file_id, sha256, storage_key, original_name_redacted, detected_mime,
            byte_count, intake_source, status, pii_status, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id, digest, storage_key, ext or ".bin", mime, size, source,
            status, pii_status, _now(),
        ),
    )


def _daily_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM memory_files
        WHERE substr(received_at, 1, 10) = ?
        """,
        (_today(),),
    ).fetchone()
    return int(row["n"])


def ingest_bytes(
    data: bytes,
    suffix: str,
    *,
    root: Path | None = None,
    source: str = "inbox",
    conn: sqlite3.Connection | None = None,
) -> IntakeResult:
    """Validate bytes and either quarantine them or store them for review."""
    layout = ensure_layout(root)
    own_conn = conn is None
    if conn is None:
        conn = connect_memory(layout)
    try:
        return _ingest(conn, layout, data, suffix.lower(), source)
    finally:
        if own_conn:
            conn.commit()
            conn.close()


def _ingest(
    conn: sqlite3.Connection,
    layout: Path,
    data: bytes,
    suffix: str,
    source: str,
) -> IntakeResult:
    if len(data) > MAX_BYTES:
        return IntakeResult("too_large")
    digest = hashlib.sha256(data).hexdigest()
    existing = conn.execute(
        "SELECT file_id, status FROM memory_files WHERE sha256 = ?",
        (digest,),
    ).fetchone()
    if existing is not None:
        return IntakeResult("duplicate", file_id=existing["file_id"])

    file_id = uuid.uuid4().hex
    sniffed = _sniff(data)

    if suffix in _ROUTE_EXT:
        key = _write(layout / "quarantine", file_id, data)
        _insert_file(
            conn, file_id=file_id, digest=digest, storage_key=key, ext=suffix,
            mime=sniffed or "application/octet-stream", size=len(data), source=source,
            status="quarantined", pii_status="skipped",
        )
        return IntakeResult("route_structured_ingest", file_id=file_id)

    expected = _ALLOW_EXT.get(suffix)
    if expected is None or not _mime_compatible(expected, sniffed):
        key = _write(layout / "quarantine", file_id, data)
        _insert_file(
            conn, file_id=file_id, digest=digest, storage_key=key, ext=suffix,
            mime=sniffed or "application/octet-stream", size=len(data), source=source,
            status="quarantined", pii_status="skipped",
        )
        code = "rejected_executable" if sniffed == "application/x-executable" else "rejected_type"
        if sniffed == "application/zip":
            code = "rejected_archive"
        return IntakeResult(code, file_id=file_id)

    if _pii_hit(data, sniffed or expected):
        key = _write(layout / "quarantine", file_id, data)
        _insert_file(
            conn, file_id=file_id, digest=digest, storage_key=key, ext=suffix,
            mime=expected, size=len(data), source=source,
            status="quarantined", pii_status="hit",
        )
        return IntakeResult("pii_quarantine", file_id=file_id)

    if _daily_count(conn) >= DAILY_FILE_LIMIT:
        key = _write(layout / "quarantine", file_id, data)
        _insert_file(
            conn, file_id=file_id, digest=digest, storage_key=key, ext=suffix,
            mime=expected, size=len(data), source=source,
            status="quarantined", pii_status="overflow",
        )
        return IntakeResult("queue_overflow", file_id=file_id)

    key = _write(layout / "files", file_id, data)
    scan = _malware_code(layout / "files" / file_id)
    if scan is not None:
        dest = layout / "quarantine" / file_id
        (layout / "files" / file_id).replace(dest)
        os.chmod(dest, 0o600)
        _insert_file(
            conn, file_id=file_id, digest=digest, storage_key=f"quarantine/{file_id}",
            ext=suffix, mime=expected, size=len(data), source=source,
            status="quarantined", pii_status="clear",
        )
        return IntakeResult(scan, file_id=file_id)

    _insert_file(
        conn, file_id=file_id, digest=digest, storage_key=key, ext=suffix,
        mime=expected, size=len(data), source=source,
        status="stored", pii_status="clear",
    )
    claim_id = _extract(conn, file_id, data, expected)
    return IntakeResult("stored", file_id=file_id, claim_id=claim_id)


def _extract(conn: sqlite3.Connection, file_id: str, data: bytes, mime: str) -> str | None:
    flags: list[str] = []
    transcript_hash = None
    status = "needs_operator"
    claim_id = None
    if mime in _TEXT_COMPAT or mime == "text/plain":
        text = data.decode("utf-8")
        transcript_hash = hashlib.sha256(text.encode()).hexdigest()
        flags = instruction_flags(text)
        block = parse_claim_block(text)
        if block is None:
            status = "needs_operator"
        else:
            try:
                proposed = propose_claim(
                    conn, block, file_id=file_id, excerpt=text,
                )
            except ClaimError:
                status = "invalid_claim"
            else:
                status = "proposed"
                claim_id = proposed.claim_id
        conn.execute(
            "UPDATE memory_files SET status = 'extracted' WHERE file_id = ?",
            (file_id,),
        )
    extraction_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO memory_extractions (
            extraction_id, file_id, extractor_version, transcript_hash,
            extraction_status, injection_flags_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            extraction_id, file_id, EXTRACTOR_VERSION, transcript_hash, status,
            json.dumps(flags), _now(),
        ),
    )
    return claim_id


def ingest_inbox(root: Path | None = None) -> list[IntakeResult]:
    layout = ensure_layout(root)
    results: list[IntakeResult] = []
    inbox = layout / "inbox"
    conn = connect_memory(layout)
    try:
        for path in sorted(inbox.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            data = path.read_bytes()
            result = _ingest(conn, layout, data, path.suffix.lower(), "inbox")
            results.append(result)
            path.unlink()
        conn.commit()
    finally:
        conn.close()
    return results


def delete_file(conn: sqlite3.Connection, file_id: str, *, root: Path | None = None) -> str:
    layout = ensure_layout(root)
    row = conn.execute(
        "SELECT storage_key, status FROM memory_files WHERE file_id = ?",
        (file_id,),
    ).fetchone()
    if row is None:
        return "missing"
    path = layout / row["storage_key"]
    if path.exists():
        path.unlink()
    conn.execute(
        """
        UPDATE memory_files
        SET status = 'deleted', deleted_at = ?, storage_key = 'deleted'
        WHERE file_id = ?
        """,
        (_now(), file_id),
    )
    return "deleted"


def export_file(conn: sqlite3.Connection, file_id: str, dest: Path, *, root: Path | None = None) -> Path:
    from src.memory.paths import assert_private_root

    layout = ensure_layout(root)
    dest = assert_private_root(dest if dest.suffix else dest)
    if dest.is_dir():
        raise ValueError("export_dest_directory")
    row = conn.execute(
        "SELECT storage_key, status FROM memory_files WHERE file_id = ?",
        (file_id,),
    ).fetchone()
    if row is None or row["status"] == "deleted":
        raise ValueError("missing")
    source = layout / row["storage_key"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    os.chmod(dest, 0o600)
    return dest


def backup_database(dest: Path, *, root: Path | None = None) -> Path:
    from src.memory.paths import assert_private_root

    layout = ensure_layout(root)
    dest = assert_private_root(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = connect_memory(layout)
    target = sqlite3.connect(str(dest))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    os.chmod(dest, 0o600)
    return dest


def status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    files = {
        row["status"]: int(row["n"])
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM memory_files GROUP BY status"
        )
    }
    claims = {
        row["status"]: int(row["n"])
        for row in conn.execute(
            """
            SELECT c.status, COUNT(*) AS n FROM memory_claims c
            JOIN (
                SELECT claim_id, MAX(revision) AS revision
                FROM memory_claims GROUP BY claim_id
            ) latest
              ON c.claim_id = latest.claim_id AND c.revision = latest.revision
            GROUP BY c.status
            """
        )
    }
    return {
        "files_stored": files.get("stored", 0) + files.get("extracted", 0),
        "files_quarantined": files.get("quarantined", 0),
        "claims_proposed": claims.get("proposed", 0),
        "claims_active": claims.get("active", 0),
        "claims_conflicted": claims.get("conflicted", 0),
    }
