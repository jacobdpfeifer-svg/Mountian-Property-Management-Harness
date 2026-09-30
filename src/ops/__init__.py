"""Operations layer: can we profitably and reliably service the stay a price creates?

Everything here is read-only with respect to Guesty. It derives turns from the
reservation calendar, costs them from property profiles and imported task
outcomes, tracks property readiness and incidents, and hands pricing a small set
of conservative inputs. It never writes rates, availability, or reservations.
Doctrine: docs/rules/OPERATIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SERVICE_TYPES = ("turnover", "inspection", "spa", "snow", "maintenance", "laundry")


@dataclass(frozen=True)
class OpsProfile:
    """Per-property turnover requirements. Minutes are worker-minutes."""

    property_id: str
    version: str
    checkout_time: str
    checkin_time: str
    base_clean_minutes: int
    inspection_minutes: int = 0
    laundry_mode: str = "onsite"
    laundry_minutes: int = 0
    hot_tub_reset_minutes: int = 0
    snow_clearance_required: bool = False
    snow_clearance_minutes: int = 0
    access_zone: str = "default"
    travel_minutes: int = 0
    crew_size: int = 1
    labor_rate_per_hour: float | None = None
    fixed_cost_per_turn: float = 0.0
    laundry_cost_per_turn: float = 0.0
    hot_tub_cost_per_turn: float = 0.0
    snow_cost_per_visit: float = 0.0
    basis: str = "estimate"

    def worker_minutes(self, *, snow: bool = False) -> float:
        total = (
            self.base_clean_minutes
            + self.inspection_minutes
            + (self.laundry_minutes if self.laundry_mode == "onsite" else 0)
            + self.hot_tub_reset_minutes
        )
        if snow and self.snow_clearance_required:
            total += self.snow_clearance_minutes
        return float(total)

    def elapsed_minutes(self, *, snow: bool = False) -> float:
        """Wall-clock minutes for the crew on site. Travel is added separately."""
        return self.worker_minutes(snow=snow) / max(1, int(self.crew_size))

    def estimated_cost(self, *, snow: bool = False) -> float:
        labor = 0.0
        if self.labor_rate_per_hour:
            labor = self.worker_minutes(snow=snow) / 60.0 * float(self.labor_rate_per_hour)
            labor += self.travel_minutes / 60.0 * float(self.labor_rate_per_hour) * max(
                1, int(self.crew_size)
            )
        total = labor + self.fixed_cost_per_turn + self.laundry_cost_per_turn
        if self.hot_tub_reset_minutes:
            total += self.hot_tub_cost_per_turn
        if snow and self.snow_clearance_required:
            total += self.snow_cost_per_visit
        return round(total, 2)


@dataclass
class TurnoverOutcome:
    """One completed (or failed) service task, normalized from any source."""

    property_id: str
    service_date: str
    source: str
    source_task_id: str
    service_type: str = "turnover"
    turn_id: str | None = None
    scheduled_start: str | None = None
    completed_at: str | None = None
    required_minutes: float | None = None
    actual_minutes: float | None = None
    cost: float | None = None
    qa_pass: bool | None = None
    rework_minutes: float | None = None
    late_ready_minutes: float | None = None
    assignee_ref: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapacitySnapshot:
    as_of: str
    service_date: str
    access_zone: str
    available_worker_minutes: float
    committed_worker_minutes: float = 0.0
    service_type: str = "turnover"
    source: str = "manual"
    confidence: float = 0.5


@dataclass
class AssetEvent:
    property_id: str
    system_type: str
    observed_at: str
    severity: str
    source_type: str
    effective_from: str | None = None
    effective_to: str | None = None
    source_ref: str | None = None
    reading: dict[str, Any] = field(default_factory=dict)
    event_id: str | None = None
    verified_by: str | None = None
