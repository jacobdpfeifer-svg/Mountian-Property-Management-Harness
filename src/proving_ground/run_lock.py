"""One market simulation at a time, cleaned up by the lock owner's PID.

A second ``proving-ground market`` refuses to start while this lock is held
by a live process. Cleanup signals that PID and its Python children. It does
not search the process table for a command-line pattern.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

LOCK_PATH = Path.home() / "wp-price-runs" / "market_sim" / "RUN.lock"


def _command(pid: int) -> str | None:
    out = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return None
    text = out.stdout.strip()
    return text or None


def _process_start(pid: int) -> str | None:
    out = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return None
    text = out.stdout.strip()
    return text or None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _process_parents() -> dict[int, int]:
    out = subprocess.run(
        ["ps", "-ax", "-o", "pid=,ppid="],
        capture_output=True,
        text=True,
        check=False,
    )
    parents: dict[int, int] = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        pid, ppid = int(parts[0]), int(parts[1])
        parents[pid] = ppid
    return parents


def descendant_pids(root: int) -> list[int]:
    """Children of ``root``, leaves last so a caller can signal them first."""
    parents = _process_parents()
    children: dict[int, list[int]] = {}
    for pid, ppid in parents.items():
        children.setdefault(ppid, []).append(pid)
    ordered: list[int] = []

    def walk(pid: int) -> None:
        for child in children.get(pid, []):
            walk(child)
            ordered.append(child)

    walk(root)
    return ordered


def read_lock(path: Path | None = None) -> dict[str, Any] | None:
    path = path or LOCK_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"pid": None, "corrupt": True, "path": str(path)}


def _write_lock(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".lock.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _claim_lock(path: Path, payload: dict[str, Any]) -> None:
    """Create the lock without a check-then-write race."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        raise
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


@contextmanager
def market_run_lock(
    output_dir: Path,
    argv: list[str] | None = None,
    *,
    path: Path | None = None,
) -> Iterator[dict[str, Any]]:
    """Hold the global market-sim lock for this process. Reclaim it if the owner is dead."""
    path = path or LOCK_PATH
    payload = {
        "pid": os.getpid(),
        "process_start": _process_start(os.getpid()),
        "output_dir": str(output_dir),
        "argv": argv or [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "reclaimed_stale_lock": None,
    }
    # Reclaim only a lock whose owner is definitely gone. The atomic create is
    # the important part: two simultaneous starts cannot both pass a read and
    # then overwrite each other's lock.
    while True:
        try:
            _claim_lock(path, payload)
            break
        except FileExistsError:
            existing = read_lock(path)
            if existing is None:
                continue
            if existing.get("corrupt"):
                raise RuntimeError(
                    f"market simulation lock {path} is corrupt; inspect or remove it manually"
                )
            owner = int(existing.get("pid") or 0)
            if owner == os.getpid() or _pid_alive(owner):
                raise RuntimeError(
                    "a market simulation is already running "
                    f"(pid {owner}, output {existing.get('output_dir')}). "
                    "Stop that PID, or rerun the same command with --resume after it exits. "
                    "Do not use a command-line pattern kill; it will hit every market sim."
                )
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            payload["reclaimed_stale_lock"] = existing
    previous = signal.getsignal(signal.SIGTERM)

    def _on_term(signum: int, frame: Any) -> None:
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _on_term)
    try:
        yield payload
    finally:
        signal.signal(signal.SIGTERM, previous)
        current = read_lock(path)
        if current and int(current.get("pid") or 0) == os.getpid():
            path.unlink(missing_ok=True)


def stop_market_run(*, path: Path | None = None) -> str:
    """Signal the lock owner and its Python descendants. Refuse a recycled PID."""
    path = path or LOCK_PATH
    existing = read_lock(path)
    if not existing or not existing.get("pid"):
        if path.exists():
            path.unlink(missing_ok=True)
        return "no market simulation lock is held"
    pid = int(existing["pid"])
    if not _pid_alive(pid):
        path.unlink(missing_ok=True)
        return f"pid {pid} is already gone; removed the stale lock"
    command = _command(pid) or ""
    expected_start = existing.get("process_start")
    actual_start = _process_start(pid)
    if expected_start and actual_start and expected_start != actual_start:
        raise RuntimeError(
            f"pid {pid} has been recycled since the market lock was written; "
            "the lock was left in place"
        )
    if "market" not in command:
        raise RuntimeError(
            f"pid {pid} is no longer a market simulation ({command or 'no command'}). "
            "The lock was left in place so a recycled PID is not signalled."
        )
    targets = [child for child in descendant_pids(pid) if "python" in (_command(child) or "").lower()]
    for child in targets:
        os.kill(child, signal.SIGTERM)
    os.kill(pid, signal.SIGTERM)
    return (
        f"signalled market sim pid {pid}"
        + (f" and {len(targets)} python child process(es)" if targets else "")
        + f" for {existing.get('output_dir')}"
    )
