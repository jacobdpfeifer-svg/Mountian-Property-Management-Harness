"""Engine-version archive (Darwin Gödel Machine style)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "data" / "proving_ground" / "archive"


def archive_run(engine_version: str, run_dir: Path) -> Path:
    dest = ARCHIVE / engine_version / run_dir.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(run_dir, dest)
    meta = {"engine_version": engine_version, "run_id": run_dir.name}
    (dest / "archive_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return dest
