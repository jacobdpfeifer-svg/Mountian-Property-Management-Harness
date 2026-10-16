"""The publish scanner must catch what it claims to catch."""

from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("scan_repo", Path(__file__).parents[2] / "scripts" / "scan_repo.py")
scan_repo = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(scan_repo)


def test_scanner_flags_planted_problems(tmp_path, monkeypatch):
    monkeypatch.setattr(scan_repo, "ROOT", tmp_path)
    files = {
        # Assembled at runtime so this file itself never matches the scanner.
        "a.py": "client_" + 'secret = "' + "abcdefghijklmnopqrstu" + '"\n',
        "b.md": "contact real.person" + "@" + "gmail.com\n",
        "c.txt": "-----BEGIN RSA " + "PRIVATE KEY-----\n",
        "d.txt": "whsec_" + "A" * 32 + "\n",
        "config/local/listings.yaml": "x: y\n",
        "data/exports/rate_card.yaml": "x: y\n",
        "ok.md": "nobody@example.com and no secrets\n",
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    problems = scan_repo.scan(sorted(files))
    flagged = {p.split(":")[0] for p in problems}
    assert flagged == set(files) - {"ok.md"}
    assert not any("real.person" in p for p in problems)   # report never echoes the address
