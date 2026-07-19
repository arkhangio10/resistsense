from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FinalStatus(StrEnum):
    PROBABLE_FAILURE = "probable_failure"
    PROBABLE_EFFICACY = "probable_efficacy"
    NO_CALL = "no_call"


class EvidenceLevel(StrEnum):
    KNOWN_MECHANISM = "A_known_mechanism"
    BIOLOGICAL_AND_STATISTICAL = "B_biological_and_statistical"
    STATISTICAL_ASSOCIATION = "C_statistical_association"
    CONFLICTING = "D_conflicting"
    INSUFFICIENT = "E_insufficient"


class TargetStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class MarkerEvidence(BaseModel):
    symbol: str
    element_type: str = "AMR"
    subtype: str | None = None
    method: str = "AMRFinderPlus"
    identity: float | None = None
    coverage: float | None = None
    resistance_class: str | None = None
    subclass: str | None = None


class FastaQcReport(BaseModel):
    passed: bool
    sha256: str
    filename: str
    total_length_bp: int
    contigs: int
    ambiguous_bases: int
    ambiguous_fraction: float
    invalid_characters: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class AnnotationReport(BaseModel):
    available: bool
    tool: str = "AMRFinderPlus"
    tool_version: str | None = None
    database_version: str | None = None
    markers: list[MarkerEvidence] = Field(default_factory=list)
    error: str | None = None


class AntibioticResult(BaseModel):
    antibiotic: str
    final_status: FinalStatus
    calibrated_probability_resistant: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    conformal_set: list[str] = Field(default_factory=list)
    evidence_level: EvidenceLevel
    target_status: TargetStatus
    target_class: str | None = None
    known_markers: list[MarkerEvidence] = Field(default_factory=list)
    model_probabilities: dict[str, float] = Field(default_factory=dict)
    ood_score: float | None = Field(default=None, ge=0, le=1)
    no_call_reasons: list[str] = Field(default_factory=list)
    explanation: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    project: str = "ResistSense"
    species: str
    research_use_only: bool = True
    disclaimer: str
    qc: FastaQcReport
    annotation: AnnotationReport
    results: list[AntibioticResult]
