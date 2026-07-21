from __future__ import annotations

from .schemas import (
    AnalysisResponse,
    AnnotationReport,
    AntibioticResult,
    EvidenceLevel,
    FastaQcReport,
    FinalStatus,
    MarkerEvidence,
    TargetStatus,
)


PREDICTIONS_SHA256 = "0c5c0fa157d89eefb08a9861eb36c057eb122775ef35b140b56a6f729a04f28f"


def verified_demo_payload() -> dict:
    """Return a frozen, precomputed judge example without shipping its FASTA."""
    markers = {
        symbol: MarkerEvidence(symbol=symbol, method="AMRFinderPlus")
        for symbol in ("blaEC", "blaTEM-1", "dfrA5", "sul2")
    }
    analysis = AnalysisResponse(
        analysis_id="verified-562-100025-v1",
        species="Escherichia coli",
        disclaimer=(
            "Research prototype. Confirm every antibiotic-response result with "
            "standard laboratory testing. This system does not recommend treatment."
        ),
        qc=FastaQcReport(
            passed=True,
            sha256="7efbbfad562dddde187c9517a14173e16eb2d26af57b184b8bbed1dc8025fbcd",
            filename="verified_ecoli_demo.fna",
            total_length_bp=4_906_368,
            contigs=149,
            ambiguous_bases=0,
            ambiguous_fraction=0.0,
        ),
        annotation=AnnotationReport(
            available=True,
            tool="AMRFinderPlus",
            tool_version="pinned ncbi/amr container",
            markers=list(markers.values()),
        ),
        results=[
            AntibioticResult(
                antibiotic="ampicillin",
                final_status=FinalStatus.PROBABLE_FAILURE,
                calibrated_probability_resistant=0.976611464951813,
                confidence=0.976611464951813,
                conformal_set=["resistant"],
                evidence_level=EvidenceLevel.BIOLOGICAL_AND_STATISTICAL,
                target_status=TargetStatus.PRESENT,
                target_class="penicillin-binding proteins",
                known_markers=[markers["blaEC"], markers["blaTEM-1"]],
                model_probabilities={"logistic_regression": 0.976762882120368},
                ood_score=0.5601374570446735,
                explanation=(
                    "Resistance signal: calibrated statistical evidence is "
                    "compatible with resistance and known markers were observed. "
                    "Confirm with standard laboratory testing."
                ),
            ),
            AntibioticResult(
                antibiotic="ciprofloxacin",
                final_status=FinalStatus.PROBABLE_EFFICACY,
                calibrated_probability_resistant=0.005431620048043904,
                confidence=0.9945683799519561,
                conformal_set=["susceptible"],
                evidence_level=EvidenceLevel.BIOLOGICAL_AND_STATISTICAL,
                target_status=TargetStatus.PRESENT,
                target_class="DNA gyrase and topoisomerase IV",
                model_probabilities={
                    "logistic_regression": 0.00043231040123999494,
                    "hist_gradient_boosting": 0.0018145348230243258,
                },
                ood_score=0.6288659793814433,
                explanation=(
                    "Susceptibility-compatible signal: statistical evidence passed "
                    "the target and confidence gates. This is not proof of efficacy. "
                    "Confirm with standard laboratory testing."
                ),
            ),
            AntibioticResult(
                antibiotic="cefotaxime",
                final_status=FinalStatus.PROBABLE_EFFICACY,
                calibrated_probability_resistant=0.0028135630425767458,
                confidence=0.9971864369574233,
                conformal_set=["susceptible"],
                evidence_level=EvidenceLevel.BIOLOGICAL_AND_STATISTICAL,
                target_status=TargetStatus.PRESENT,
                target_class="penicillin-binding protein 3",
                model_probabilities={
                    "logistic_regression": 0.0001336047824830117
                },
                ood_score=0.5601374570446735,
                explanation=(
                    "Susceptibility-compatible signal: statistical evidence passed "
                    "the target and confidence gates. This is not proof of efficacy. "
                    "Confirm with standard laboratory testing."
                ),
            ),
            AntibioticResult(
                antibiotic="gentamicin",
                final_status=FinalStatus.PROBABLE_EFFICACY,
                calibrated_probability_resistant=0.0002611072164619541,
                confidence=0.999738892783538,
                conformal_set=["susceptible"],
                evidence_level=EvidenceLevel.BIOLOGICAL_AND_STATISTICAL,
                target_status=TargetStatus.PRESENT,
                target_class="bacterial 16S rRNA",
                model_probabilities={
                    "logistic_regression": 0.00043990095363123926
                },
                ood_score=0.5601374570446735,
                explanation=(
                    "Susceptibility-compatible signal: statistical evidence passed "
                    "the target and confidence gates. This is not proof of efficacy. "
                    "Confirm with standard laboratory testing."
                ),
            ),
            AntibioticResult(
                antibiotic="trimethoprim/sulfamethoxazole",
                final_status=FinalStatus.NO_CALL,
                calibrated_probability_resistant=0.6562818727577711,
                confidence=None,
                conformal_set=["resistant"],
                evidence_level=EvidenceLevel.INSUFFICIENT,
                target_status=TargetStatus.PRESENT,
                target_class="folate biosynthesis",
                known_markers=[markers["dfrA5"], markers["sul2"]],
                model_probabilities={"logistic_regression": 0.9527303628345879},
                ood_score=0.5601374570446735,
                no_call_reasons=["probability_inside_abstention_region"],
                explanation=(
                    "No-call — insufficient or conflicting evidence: the calibrated "
                    "probability remained inside the abstention region. Standard "
                    "laboratory testing is required."
                ),
            ),
        ],
    )
    return {
        "demo_mode": "precomputed_verified_frozen_test_case",
        "label": "Verified judge example — not a newly uploaded FASTA analysis",
        "provenance": {
            "source": "BV-BRC laboratory-only self-curated cohort",
            "sample_id": "562.100025",
            "genetic_group": "7429",
            "split": "frozen_grouped_test",
            "predictions_sha256": PREDICTIONS_SHA256,
            "precomputed": True,
            "test_set_retuning_allowed": False,
        },
        "analysis": analysis.model_dump(mode="json"),
    }
