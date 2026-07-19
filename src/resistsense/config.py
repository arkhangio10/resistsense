from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class ProjectConfig(BaseModel):
    name: str
    tagline: str
    mode: str = "research_prototype"
    mandatory_disclaimer: str


class SpeciesConfig(BaseModel):
    scientific_name: str
    taxon_id: int
    amrfinderplus_organism: str


class ScopeConfig(BaseModel):
    species: SpeciesConfig
    antibiotics: list[str] = Field(min_length=1, max_length=5)

    @field_validator("antibiotics")
    @classmethod
    def unique_antibiotics(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Antibiotics must be unique")
        return normalized


class FastaQcConfig(BaseModel):
    min_genome_length_bp: int = Field(gt=0)
    max_genome_length_bp: int = Field(gt=0)
    max_contigs: int = Field(gt=0)
    max_ambiguous_fraction: float = Field(ge=0, le=1)
    allowed_bases: str

    @field_validator("max_genome_length_bp")
    @classmethod
    def valid_length_range(cls, value: int, info: Any) -> int:
        minimum = info.data.get("min_genome_length_bp")
        if minimum is not None and value <= minimum:
            raise ValueError("Maximum genome length must exceed minimum")
        return value


class KmerConfig(BaseModel):
    enabled: bool = True
    k: int = Field(default=15, ge=7, le=31)
    buckets: int = Field(default=512, ge=32, le=8192)
    stride: int = Field(default=25, ge=1, le=1000)


class FeatureConfig(BaseModel):
    kmer: KmerConfig = Field(default_factory=KmerConfig)


class AntibioticModelPolicy(BaseModel):
    strategy: Literal["amrfinder_logistic", "full_ensemble"]
    conformal_alpha: float = Field(default=0.05, gt=0, lt=0.5)


class ModelingConfig(BaseModel):
    selection_source: Path
    antibiotics: dict[str, AntibioticModelPolicy] = Field(min_length=1)


class FirewallConfig(BaseModel):
    resistant_probability_threshold: float = Field(gt=0.5, le=1)
    susceptible_probability_threshold: float = Field(ge=0, lt=0.5)
    maximum_model_disagreement: float = Field(ge=0, le=1)
    maximum_ood_score: float = Field(ge=0, le=1)
    require_calibration: bool = True
    require_conformal_singleton: bool = True
    require_target_for_probable_efficacy: bool = True
    require_amrfinderplus: bool = True


class RuntimeConfig(BaseModel):
    model_dir: Path
    report_dir: Path
    max_upload_bytes: int = Field(gt=0)
    amrfinder_timeout_seconds: int = Field(gt=0)
    target_annotator_timeout_seconds: int = Field(default=900, gt=0)


class ResistSenseConfig(BaseModel):
    project: ProjectConfig
    scope: ScopeConfig
    fasta_qc: FastaQcConfig
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    modeling: ModelingConfig
    firewall: FirewallConfig
    runtime: RuntimeConfig


def _default_config_path() -> Path:
    return Path(os.getenv("RESISTSENSE_CONFIG", "configs/resistsense.yaml"))


@lru_cache(maxsize=4)
def load_config(path: str | Path | None = None) -> ResistSenseConfig:
    config_path = Path(path) if path is not None else _default_config_path()
    if not config_path.is_file():
        raise FileNotFoundError(f"ResistSense configuration not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("ResistSense configuration must be a YAML object")
    return ResistSenseConfig.model_validate(raw)
