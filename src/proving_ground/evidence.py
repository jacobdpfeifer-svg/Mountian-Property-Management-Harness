"""Evidence labels derived from source manifests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    license_class: str  # publishable | internal_only | excluded_from_sales_claims


def sources_from_manifest_files(files: list[dict[str, str]]) -> list[SourceRecord]:
    return [
        SourceRecord(f["path"], f.get("license_class", "internal_only"))
        for f in files
    ]


def compute_evidence_label(sources: list[SourceRecord]) -> str:
    """Most restrictive source wins (PROVING_GROUND_PROMPT rule 10)."""
    if not sources:
        return "internal_only"
    order = {"publishable": 0, "internal_only": 1, "excluded_from_sales_claims": 2}
    worst = max(sources, key=lambda s: order.get(s.license_class, 99))
    return worst.license_class
