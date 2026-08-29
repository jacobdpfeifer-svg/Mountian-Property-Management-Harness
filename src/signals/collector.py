"""Collector framework — every Pfeifer Optimization collector inherits this discipline.

Collectors are deterministic (or schema-bound extractors). They never touch price.
They declare a schema, fetch observations, validate (reject never clamp), and
auto-register into signal_definitions so Phase-2 packages never edit a shared registry.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Type

from src.signals.store import (
    Observation,
    SignalDefinition,
    SignalStore,
    _iso,
)
from src.signals.validate import validate_observation


@dataclass
class FieldSpec:
    name: str  # becomes signal_key suffix or full key via signal_key()
    unit: str
    value_min: float | None = None
    value_max: float | None = None
    description: str = ""


@dataclass
class CollectorSchema:
    collector_id: str
    category: str
    cadence: str
    source: str
    fields: list[FieldSpec]
    schema_version: str = "1"
    max_staleness_days: int | None = None

    def signal_key(self, field: FieldSpec) -> str:
        return f"{self.collector_id}.{field.name}"


@dataclass
class CollectorResult:
    run_id: str
    status: str
    written: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)


_REGISTRY: dict[str, Type["Collector"]] = {}


def register_collector(cls: Type["Collector"]) -> Type["Collector"]:
    _REGISTRY[cls.schema.collector_id] = cls
    return cls


def get_collector(collector_id: str) -> Type["Collector"]:
    if collector_id not in _REGISTRY:
        raise KeyError(f"unknown collector: {collector_id}")
    return _REGISTRY[collector_id]


def list_collectors() -> list[str]:
    return sorted(_REGISTRY)


class Collector(ABC):
    schema: CollectorSchema

    def __init__(self, store: SignalStore, *, sleep: Callable[[float], None] = time.sleep):
        self.store = store
        self._sleep = sleep

    def ensure_registered(self) -> None:
        """Auto-register signal_definitions from declared schema (owns only this collector)."""
        for field in self.schema.fields:
            self.store.upsert_definition(
                SignalDefinition(
                    signal_key=self.schema.signal_key(field),
                    category=self.schema.category,
                    unit=field.unit,
                    cadence=self.schema.cadence,
                    source=self.schema.source,
                    status="experimental",
                    schema_version=self.schema.schema_version,
                    description=field.description,
                    value_min=field.value_min,
                    value_max=field.value_max,
                    collector=self.schema.collector_id,
                )
            )

    @abstractmethod
    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        """Return raw observations. Validation happens in run()."""

    def run(
        self,
        as_of: date,
        market_id: str,
        *,
        retries: int = 2,
        backoff_s: float = 0.5,
    ) -> CollectorResult:
        self.ensure_registered()
        run_id = self.store.start_run(self.schema.collector_id, as_of, market_id)
        errors: list[str] = []
        raw: list[Observation] = []

        for attempt in range(retries + 1):
            try:
                raw = self.fetch(as_of, market_id)
                break
            except Exception as exc:  # noqa: BLE001 — collectors must degrade, not crash the run
                errors.append(f"attempt {attempt + 1}: {exc}")
                if attempt < retries:
                    self._sleep(backoff_s * (2**attempt))
                else:
                    self.store.finish_run(
                        run_id, status="failed", observations=0, rejected=0, errors=errors
                    )
                    return CollectorResult(run_id, "failed", 0, 0, errors)

        field_by_key = {
            self.schema.signal_key(f): f for f in self.schema.fields
        }
        accepted: list[Observation] = []
        rejected = 0
        for obs in raw:
            obs.run_id = run_id
            spec = field_by_key.get(obs.signal_key)
            vmin = spec.value_min if spec else None
            vmax = spec.value_max if spec else None
            result = validate_observation(
                obs,
                value_min=vmin,
                value_max=vmax,
                max_staleness_days=self.schema.max_staleness_days,
                as_of=_iso(as_of),
            )
            if not result.ok or result.observation is None:
                rejected += 1
                errors.append(result.reason or f"rejected {obs.signal_key}")
                # Record a failed quality row so the gap is visible — value omitted.
                failed = Observation(
                    signal_key=obs.signal_key,
                    market_id=obs.market_id,
                    observed_at=obs.observed_at,
                    effective_date=obs.effective_date,
                    value=None,
                    horizon_days=obs.horizon_days,
                    confidence=0.0,
                    quality="failed",
                    provenance_url=obs.provenance_url,
                    run_id=run_id,
                    meta={"reject_reason": result.reason},
                )
                accepted.append(failed)
                continue
            accepted.append(result.observation)

        written = self.store.write_observations(accepted)
        # Only count ok values toward "written" success semantics for status.
        ok_n = sum(1 for o in accepted if o.quality == "ok")
        if rejected and ok_n == 0:
            status = "failed"
        elif rejected:
            status = "degraded"
        else:
            status = "ok"
        self.store.finish_run(
            run_id,
            status=status,
            observations=ok_n,
            rejected=rejected,
            errors=errors,
        )
        return CollectorResult(run_id, status, written, rejected, errors)


# Import side-effect registration happens in collectors/__init__.py
