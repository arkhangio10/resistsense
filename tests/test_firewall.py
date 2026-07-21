from resistsense.config import FirewallConfig
from resistsense.firewall import DrugEvidence, decide
from resistsense.schemas import (
    EvidenceLevel,
    FastaQcReport,
    FinalStatus,
    MarkerEvidence,
    TargetStatus,
)


POLICY = FirewallConfig(
    resistant_probability_threshold=0.7,
    susceptible_probability_threshold=0.3,
    maximum_model_disagreement=0.25,
    maximum_ood_score=0.8,
)
QC = FastaQcReport(
    passed=True,
    sha256="0" * 64,
    filename="sample.fna",
    total_length_bp=5_000_000,
    contigs=50,
    ambiguous_bases=0,
    ambiguous_fraction=0,
)


def base_evidence(**overrides) -> DrugEvidence:
    values = dict(
        antibiotic="ciprofloxacin",
        qc=QC,
        annotation_available=True,
        model_available=True,
        calibrated_probability_resistant=0.91,
        calibrated=True,
        conformal_set={"resistant"},
        model_probabilities={"logistic_regression": 0.91},
        ood_score=0.2,
        target_status=TargetStatus.PRESENT,
    )
    values.update(overrides)
    return DrugEvidence(**values)


def test_missing_model_always_abstains() -> None:
    result = decide(base_evidence(model_available=False), POLICY)
    assert result.final_status is FinalStatus.NO_CALL
    assert "model_unavailable" in result.no_call_reasons
    assert result.explanation.startswith(
        "No-call — insufficient or conflicting evidence"
    )


def test_high_ood_always_abstains() -> None:
    result = decide(base_evidence(ood_score=0.95), POLICY)
    assert result.final_status is FinalStatus.NO_CALL
    assert result.evidence_level is EvidenceLevel.CONFLICTING


def test_supported_resistance_can_emit_probable_failure() -> None:
    result = decide(
        base_evidence(known_markers=[MarkerEvidence(symbol="gyrA_S83L")]),
        POLICY,
    )
    assert result.final_status is FinalStatus.PROBABLE_FAILURE
    assert result.evidence_level is EvidenceLevel.BIOLOGICAL_AND_STATISTICAL
    assert result.explanation.startswith("Resistance signal")
    assert "probable failure" not in result.explanation.lower()


def test_supported_susceptibility_uses_non_efficacy_wording() -> None:
    result = decide(
        base_evidence(
            calibrated_probability_resistant=0.12,
            conformal_set={"susceptible"},
            model_probabilities={"logistic_regression": 0.12},
            target_status=TargetStatus.PRESENT,
            known_markers=[],
        ),
        POLICY,
    )
    assert result.final_status is FinalStatus.PROBABLE_EFFICACY
    assert result.explanation.startswith("Susceptibility-compatible signal")
    assert "not proof of efficacy" in result.explanation.lower()


def test_susceptibility_requires_confirmed_target() -> None:
    result = decide(
        base_evidence(
            calibrated_probability_resistant=0.12,
            conformal_set={"susceptible"},
            model_probabilities={"logistic_regression": 0.12},
            target_status=TargetStatus.UNKNOWN,
        ),
        POLICY,
    )
    assert result.final_status is FinalStatus.NO_CALL
    assert "molecular_target_not_confirmed" in result.no_call_reasons
