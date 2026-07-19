from __future__ import annotations

from dataclasses import dataclass, field

from .config import FirewallConfig
from .schemas import (
    AntibioticResult,
    EvidenceLevel,
    FastaQcReport,
    FinalStatus,
    MarkerEvidence,
    TargetStatus,
)


@dataclass
class DrugEvidence:
    antibiotic: str
    qc: FastaQcReport
    annotation_available: bool
    model_available: bool = False
    calibrated_probability_resistant: float | None = None
    calibrated: bool = False
    conformal_set: set[str] = field(default_factory=set)
    model_probabilities: dict[str, float] = field(default_factory=dict)
    ood_score: float | None = None
    target_status: TargetStatus = TargetStatus.UNKNOWN
    target_class: str | None = None
    known_markers: list[MarkerEvidence] = field(default_factory=list)


def _no_call(
    evidence: DrugEvidence,
    reasons: list[str],
    level: EvidenceLevel = EvidenceLevel.INSUFFICIENT,
) -> AntibioticResult:
    return AntibioticResult(
        antibiotic=evidence.antibiotic,
        final_status=FinalStatus.NO_CALL,
        calibrated_probability_resistant=evidence.calibrated_probability_resistant,
        confidence=None,
        conformal_set=sorted(evidence.conformal_set),
        evidence_level=level,
        target_status=evidence.target_status,
        target_class=evidence.target_class,
        known_markers=evidence.known_markers,
        model_probabilities=evidence.model_probabilities,
        ood_score=evidence.ood_score,
        no_call_reasons=reasons,
        explanation=(
            "No-call: the available evidence does not satisfy the ResistSense "
            "safety policy. Standard laboratory testing is required."
        ),
    )


def decide(evidence: DrugEvidence, policy: FirewallConfig) -> AntibioticResult:
    reasons: list[str] = []
    if not evidence.qc.passed:
        reasons.extend(f"genome_qc:{reason}" for reason in evidence.qc.reasons)
    if not evidence.model_available:
        reasons.append("model_unavailable")
    if policy.require_amrfinderplus and not evidence.annotation_available:
        reasons.append("amrfinderplus_unavailable")
    if policy.require_calibration and not evidence.calibrated:
        reasons.append("calibration_unavailable")
    if evidence.calibrated_probability_resistant is None:
        reasons.append("probability_unavailable")
    if evidence.ood_score is None:
        reasons.append("ood_score_unavailable")
    elif evidence.ood_score > policy.maximum_ood_score:
        reasons.append("out_of_distribution")

    probabilities = list(evidence.model_probabilities.values())
    if len(probabilities) > 1:
        disagreement = max(probabilities) - min(probabilities)
        if disagreement > policy.maximum_model_disagreement:
            reasons.append("model_disagreement")

    if policy.require_conformal_singleton and len(evidence.conformal_set) != 1:
        reasons.append("conformal_set_not_singleton")

    if reasons:
        conflict_tokens = {
            "out_of_distribution",
            "model_disagreement",
            "conformal_set_not_singleton",
        }
        level = (
            EvidenceLevel.CONFLICTING
            if conflict_tokens.intersection(reasons)
            else EvidenceLevel.INSUFFICIENT
        )
        return _no_call(evidence, reasons, level)

    probability = evidence.calibrated_probability_resistant
    assert probability is not None
    conformal_label = next(iter(evidence.conformal_set))

    if (
        probability >= policy.resistant_probability_threshold
        and conformal_label == "resistant"
    ):
        level = (
            EvidenceLevel.BIOLOGICAL_AND_STATISTICAL
            if evidence.known_markers
            else EvidenceLevel.STATISTICAL_ASSOCIATION
        )
        return AntibioticResult(
            antibiotic=evidence.antibiotic,
            final_status=FinalStatus.PROBABLE_FAILURE,
            calibrated_probability_resistant=probability,
            confidence=probability,
            conformal_set=[conformal_label],
            evidence_level=level,
            target_status=evidence.target_status,
            target_class=evidence.target_class,
            known_markers=evidence.known_markers,
            model_probabilities=evidence.model_probabilities,
            ood_score=evidence.ood_score,
            explanation=(
                "Probable failure: calibrated statistical evidence supports "
                "resistance. Confirm with standard laboratory testing."
            ),
        )

    if probability <= policy.susceptible_probability_threshold:
        efficacy_reasons: list[str] = []
        if conformal_label != "susceptible":
            efficacy_reasons.append("conformal_result_not_susceptible")
        if evidence.known_markers:
            efficacy_reasons.append("known_resistance_marker_conflict")
        if (
            policy.require_target_for_probable_efficacy
            and evidence.target_status is not TargetStatus.PRESENT
        ):
            efficacy_reasons.append("molecular_target_not_confirmed")
        if efficacy_reasons:
            return _no_call(evidence, efficacy_reasons, EvidenceLevel.CONFLICTING)
        return AntibioticResult(
            antibiotic=evidence.antibiotic,
            final_status=FinalStatus.PROBABLE_EFFICACY,
            calibrated_probability_resistant=probability,
            confidence=1 - probability,
            conformal_set=[conformal_label],
            evidence_level=EvidenceLevel.BIOLOGICAL_AND_STATISTICAL,
            target_status=evidence.target_status,
            target_class=evidence.target_class,
            model_probabilities=evidence.model_probabilities,
            ood_score=evidence.ood_score,
            explanation=(
                "Probable efficacy: susceptibility evidence passed the target "
                "and confidence gates. Confirm with standard laboratory testing."
            ),
        )

    return _no_call(evidence, ["probability_inside_abstention_region"])
