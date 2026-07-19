from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .schemas import MarkerEvidence, TargetStatus


class DrugTarget(BaseModel):
    target_class: str
    required_groups: list[list[str]] = Field(min_length=1)
    resistance_classes: list[str] = Field(min_length=1)
    resistance_subclasses: list[str] = Field(default_factory=list)


class TargetCatalog(BaseModel):
    species: str
    policy: str
    antibiotics: dict[str, DrugTarget]


@lru_cache(maxsize=4)
def load_target_catalog(
    path: str | Path = "configs/drug_targets.yaml",
) -> TargetCatalog:
    target_path = Path(path)
    raw = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    return TargetCatalog.model_validate(raw)


def evaluate_target(
    antibiotic: str,
    observed_gene_symbols: set[str] | None,
    catalog: TargetCatalog,
) -> tuple[TargetStatus, DrugTarget | None]:
    target = catalog.antibiotics.get(antibiotic)
    if target is None or observed_gene_symbols is None:
        return TargetStatus.UNKNOWN, target
    observed = {symbol.lower() for symbol in observed_gene_symbols}
    groups_present = all(
        bool(observed.intersection(symbol.lower() for symbol in group))
        for group in target.required_groups
    )
    return (
        TargetStatus.PRESENT if groups_present else TargetStatus.ABSENT,
        target,
    )


def relevant_markers(
    markers: list[MarkerEvidence],
    target: DrugTarget | None,
) -> list[MarkerEvidence]:
    if target is None:
        return []
    accepted = {value.strip().upper() for value in target.resistance_classes}
    accepted_subclasses = {
        value.strip().upper() for value in target.resistance_subclasses
    }

    def subclass_matches(marker: MarkerEvidence) -> bool:
        if not accepted_subclasses:
            return True
        observed = {
            value.strip().upper()
            for value in (marker.subclass or "").split("/")
            if value.strip()
        }
        return bool(observed.intersection(accepted_subclasses))

    return [
        marker
        for marker in markers
        if marker.resistance_class
        and marker.resistance_class.strip().upper() in accepted
        and (marker.subtype or "AMR").strip().upper() in {"AMR", "POINT"}
        and subclass_matches(marker)
    ]
