"""Private operator storage. Never lives in the repo or iCloud Desktop."""

from __future__ import annotations

import os
from pathlib import Path

from src.config import ROOT

ENV_ROOT = "MONTLUXE_MEMORY_ROOT"
APP_DIR_NAME = "MontLuxePricing"


class UnsafeMemoryRoot(ValueError):
    """Raised when a memory path would land in git or iCloud."""


def default_memory_root() -> Path:
    override = os.environ.get(ENV_ROOT)
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Application Support" / APP_DIR_NAME


def assert_private_root(path: Path) -> Path:
    """Reject the pricing repo and any iCloud Drive path."""
    resolved = path.expanduser().resolve()
    repo = ROOT.resolve()
    if resolved == repo or repo in resolved.parents:
        raise UnsafeMemoryRoot(f"memory root {resolved} is inside the pricing repo")
    parts = resolved.parts
    if "Mobile Documents" in parts or any("CloudDocs" in part for part in parts):
        raise UnsafeMemoryRoot(f"memory root {resolved} is inside iCloud")
    return resolved


def ensure_layout(root: Path | None = None) -> Path:
    resolved = assert_private_root(root or default_memory_root())
    resolved.mkdir(parents=True, exist_ok=True)
    os.chmod(resolved, 0o700)
    for name in ("files", "quarantine", "inbox", "receipts"):
        folder = resolved / name
        folder.mkdir(parents=True, exist_ok=True)
        os.chmod(folder, 0o700)
    return resolved


def inbox_dir(root: Path | None = None) -> Path:
    return ensure_layout(root) / "inbox"


def receipts_dir(root: Path | None = None) -> Path:
    return ensure_layout(root) / "receipts"
