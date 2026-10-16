from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.db import connect, init_db
from src.db.migrations import apply_migrations
from src.security.scope import PortfolioScope

PROPS = frozenset({"summit_haus", "overlook_ridge", "cloud_9"})


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "sec.db"
    init_db(path, seed_markets=False)
    c = connect(path)
    apply_migrations(c)
    yield c
    c.close()


@pytest.fixture
def scope() -> PortfolioScope:
    return PortfolioScope(PROPS, {"LST-A": "summit_haus", "LST-B": "overlook_ridge", "LST-C": "cloud_9"})


@pytest.fixture
def control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "control"
    d.mkdir()
    monkeypatch.setenv("WP_PRICE_CONTROL_DIR", str(d))
    monkeypatch.delenv("WP_PRICE_ENV", raising=False)
    return d


def write_permit(control: Path, **over) -> None:
    permit = {"permit_id": "P-1", "approved_by": "operator", "writes_enabled": True,
              "environment": "production", "property_ids": ["summit_haus"],
              "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
    permit.update(over)
    (control / "write_permit.json").write_text(json.dumps(permit))
