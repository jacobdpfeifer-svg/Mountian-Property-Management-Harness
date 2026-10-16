#!/usr/bin/env python3
"""Fail if a secret, guest identity, or confidential file would be published.

Scans every file Git tracks or would add (tracked + untracked, not ignored).
Git history is out of scope: older commits are known to contain listing ids
(see docs/reports/final_delivery/PLATFORM_READINESS.md); purging them needs a
history rewrite and force push, which only the repository owner can authorize.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATHS = [
    re.compile(p) for p in (
        r"^\.env$", r"^config/local/(listings|aliases)\.yaml$", r"^data/exports/", r"^data/cloud9/",
        r"^data/dec2023/", r"\.db$", r"\.sqlite3?$", r"(^|/)guesty_token", r"write_permit\.json$",
    )
]
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "svix secret": re.compile(r"whsec_(?!\" \+|\$|<)[A-Za-z0-9+/]{20,}"),
    "bearer token": re.compile(r"Bearer [A-Za-z0-9._-]{30,}"),
    "assigned secret": re.compile(
        r"(?i)(client_secret|api_key|password|token)\s*[:=]\s*['\"][A-Za-z0-9/+_.-]{16,}['\"]"),
    "aws key": re.compile(r"AKIA[0-9A-Z]{16}"),
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ALLOWED_EMAIL = re.compile(r"(@example\.(com|org)|noreply@|@anthropic\.com|^t@t$|@b\.co$)")
SKIP_SUFFIXES = {".png", ".jpg", ".pdf", ".gz", ".zip", ".lock"}


def candidate_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
                         check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line and (ROOT / line).is_file()]


def scan(files: list[str]) -> list[str]:
    problems = []
    for name in files:
        if any(p.search(name) for p in FORBIDDEN_PATHS):
            problems.append(f"{name}: confidential path must not be published")
            continue
        if Path(name).suffix in SKIP_SUFFIXES:
            continue
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                problems.append(f"{name}: possible {label}")
        for email in set(EMAIL.findall(text)):
            if not ALLOWED_EMAIL.search(email) and not email.endswith((".py", ".md", ".yaml")):
                problems.append(f"{name}: email address {email[:3]}***")
    return problems


def main() -> int:
    problems = scan(candidate_files())
    for p in problems:
        print(p)
    print(f"scan_repo: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
