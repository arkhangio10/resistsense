from __future__ import annotations

from .schemas import AnalysisResponse, FinalStatus


FORBIDDEN_TREATMENT_PHRASES = (
    "prescribe",
    "recommended treatment",
    "administer",
    "guaranteed to work",
    "will work",
)


def audit_report(response: AnalysisResponse) -> list[str]:
    """Return communication-policy violations without changing scientific data."""
    violations: list[str] = []
    disclaimer = response.disclaimer.lower()
    if "laboratory" not in disclaimer or "research" not in disclaimer:
        violations.append("missing_research_and_laboratory_disclaimer")
    for result in response.results:
        text = result.explanation.lower()
        if any(phrase in text for phrase in FORBIDDEN_TREATMENT_PHRASES):
            violations.append(f"unsafe_treatment_language:{result.antibiotic}")
        if result.final_status is FinalStatus.NO_CALL and not result.no_call_reasons:
            violations.append(f"no_call_without_reason:{result.antibiotic}")
        if "laboratory" not in text:
            violations.append(f"missing_lab_confirmation:{result.antibiotic}")
    return violations
