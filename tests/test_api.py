import asyncio
import json

import httpx

from resistsense.api import _cors_origins, app


def request(method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_cors_origins_can_be_configured(monkeypatch) -> None:
    monkeypatch.setenv(
        "RESISTSENSE_CORS_ORIGINS",
        "https://demo.example, https://api.example/,https://demo.example",
    )
    assert _cors_origins() == ["https://api.example", "https://demo.example"]


def test_health_and_scope() -> None:
    assert request("GET", "/health").json()["ok"] is True
    scope = request("GET", "/api/v1/scope")
    assert scope.status_code == 200
    assert scope.json()["project"] == "ResistSense"
    assert len(scope.json()["antibiotics"]) == 5


def test_usage_endpoint_accepts_only_anonymous_uuid(monkeypatch) -> None:
    monkeypatch.setattr(
        "resistsense.api.record_anonymous_visitor",
        lambda visitor_id: {
            "available": True,
            "unique_anonymous_browsers": 7,
            "new_visitor": True,
            "reason": None,
            "privacy": "No personal data is stored.",
        },
    )
    response = request(
        "POST",
        "/api/v1/usage/visit",
        json={"visitor_id": "c5690b0f-207c-45a8-bf05-daf30f5303a9"},
    )
    assert response.status_code == 200
    assert response.json()["unique_anonymous_browsers"] == 7
    assert response.json()["new_visitor"] is True
    assert request(
        "POST", "/api/v1/usage/visit", json={"visitor_id": "not-a-uuid"}
    ).status_code == 422


def test_verified_demo_is_precomputed_traceable_and_safe() -> None:
    response = request("GET", "/api/v1/verified-demo")
    assert response.status_code == 200
    payload = response.json()
    assert payload["demo_mode"] == "precomputed_verified_frozen_test_case"
    assert payload["provenance"]["split"] == "frozen_grouped_test"
    assert payload["provenance"]["test_set_retuning_allowed"] is False
    assert len(payload["provenance"]["predictions_sha256"]) == 64
    statuses = {
        item["final_status"] for item in payload["analysis"]["results"]
    }
    assert statuses == {"probable_failure", "probable_efficacy", "no_call"}
    assert all(
        "laboratory" in item["explanation"].lower()
        for item in payload["analysis"]["results"]
    )


def test_dataset_audit_exposes_only_aggregate_verified_data(
    monkeypatch, tmp_path
) -> None:
    summary = tmp_path / "curated_summary.json"
    summary.write_text(
        json.dumps(
            {
                "status": "self_curated_frozen_cohort",
                "source": "test fixture",
                "species": "Escherichia coli",
                "samples": 2909,
                "genetic_groups": 1306,
                "manifest_sha256": "fixture",
                "split_counts": {"train": 2000, "test": 437},
                "curation_version": "test",
                "balance": [
                    {
                        "antibiotic": antibiotic,
                        "resistant": 100,
                        "susceptible": 200,
                    }
                    for antibiotic in (
                        "ampicillin",
                        "cefotaxime",
                        "ciprofloxacin",
                        "gentamicin",
                        "trimethoprim/sulfamethoxazole",
                    )
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RESISTSENSE_PHASE2_SUMMARY", str(summary))
    response = request("GET", "/api/v1/dataset-audit")
    assert response.status_code == 200
    payload = response.json()
    assert payload["unique_genomes"] == 2909
    assert len(payload["antibiotics"]) == 5
    assert payload["status"] in {
        "self_curated_candidate_cohort",
        "self_curated_frozen_cohort",
    }
    assert "conflict_examples" not in payload


def test_prediction_autopsy_exposes_real_held_out_errors_safely(
    monkeypatch, tmp_path
) -> None:
    artifact = tmp_path / "prediction_autopsy.json"
    summary = {
        "ampicillin": {"base_errors": 20},
        "cefotaxime": {"base_errors": 8},
        "ciprofloxacin": {"base_errors": 5},
        "gentamicin": {"base_errors": 14},
        "trimethoprim/sulfamethoxazole": {"base_errors": 21},
    }
    cases = [
        {
            "category": "prevented_error" if index % 2 == 0 else "escaped_error",
            "narrative": "Standard laboratory testing is required.",
        }
        for index in range(9)
    ]
    artifact.write_text(
        json.dumps(
            {
                "status": "frozen_grouped_test_errors",
                "source": "test fixture",
                "selection_policy": "deterministic fixture",
                "disclaimer": "Research use only.",
                "summary": summary,
                "cases": cases,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RESISTSENSE_PREDICTION_AUTOPSY", str(artifact))
    response = request("GET", "/api/v1/prediction-autopsy")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "frozen_grouped_test_errors"
    assert len(payload["cases"]) == 9
    assert sum(item["base_errors"] for item in payload["summary"].values()) == 68
    assert {item["category"] for item in payload["cases"]} == {
        "prevented_error",
        "escaped_error",
    }
    assert all(
        "standard laboratory testing" in item["narrative"].lower()
        for item in payload["cases"]
    )
    assert all("sequence" not in item for item in payload["cases"])


def test_class_aware_safety_report_preserves_release_boundary(
    monkeypatch, tmp_path
) -> None:
    artifact = tmp_path / "class_aware_safety_report.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": "frozen_internal_grouped_validation",
                "research_demo_status": "pass",
                "clinical_release_status": "fail_not_externally_validated",
                "clinical_release_reasons": [
                    "independent_external_validation_incomplete"
                ],
                "source": "test fixture",
                "predictions_sha256": "fixture",
                "evaluation_scope": {
                    "external_validation_complete": False,
                    "test_set_retuning_allowed": False,
                },
                "limitations": ["Laboratory confirmation is required."],
                "antibiotics": {
                    "gentamicin": {
                        "by_laboratory_class": {
                            "resistant": {
                                "coverage": {
                                    "numerator": 0,
                                    "denominator": 27,
                                    "value": 0.0,
                                }
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RESISTSENSE_SAFETY_REPORT", str(artifact))
    response = request("GET", "/api/v1/safety-report")
    assert response.status_code == 200
    payload = response.json()
    assert payload["research_demo_status"] == "pass"
    assert payload["clinical_release_status"] == "fail_not_externally_validated"
    assert payload["evaluation_scope"]["test_set_retuning_allowed"] is False
    resistant = payload["antibiotics"]["gentamicin"]["by_laboratory_class"][
        "resistant"
    ]
    assert resistant["coverage"]["numerator"] == 0
    assert resistant["coverage"]["denominator"] == 27


def test_short_fasta_returns_safe_no_calls() -> None:
    response = request(
        "POST",
        "/api/v1/analyze",
        files={"file": ("short.fasta", b">short\nACGTACGT\n", "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["qc"]["passed"] is False
    assert all(result["final_status"] == "no_call" for result in payload["results"])


def test_evidence_audit_falls_back_without_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    scientific = request(
        "POST",
        "/api/v1/analyze",
        files={"file": ("short.fasta", b">short\nACGTACGT\n", "text/plain")},
    ).json()
    response = request("POST", "/api/v1/evidence-audit", json=scientific)
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "deterministic_fallback"
    assert payload["fallback_reason"] == "openai_api_key_missing"
    assert payload["audit"]["laboratory_confirmation_required"] is True
    assert all(
        item["final_status"] == "no_call"
        for item in payload["audit"]["result_checks"]
    )
    assert "short.fasta" not in json.dumps(payload)


def test_auditor_safety_eval_executes_all_guardrail_cases() -> None:
    response = request("GET", "/api/v1/auditor-safety-eval")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_mode"] == "executable deterministic guardrail tests"
    assert payload["total_cases"] >= 10
    assert payload["passed_cases"] == payload["total_cases"]
    assert payload["failed_cases"] == 0
    assert payload["metrics"]["decision_integrity"]["passed"] >= 3
    assert payload["metrics"]["privacy_boundary"] == {"passed": 2, "total": 2}
    assert all(case["passed"] for case in payload["cases"])


def test_system_provenance_exposes_versions_without_secrets() -> None:
    response = request("GET", "/api/v1/system-provenance")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["policy"]["sha256"]) == 64
    assert payload["policy"]["fail_safe"] is True
    assert payload["auditor"]["raw_fasta_sent_to_openai"] is False
    assert payload["auditor"]["decision_mutation_allowed"] is False
    assert payload["release_boundary"]["laboratory_confirmation_required"] is True
    assert payload["release_boundary"]["treatment_recommendation_allowed"] is False
    serialized = json.dumps(payload).lower()
    assert "openai_api_key" not in serialized
    assert "secret" not in serialized


def test_non_fasta_extension_is_rejected() -> None:
    response = request(
        "POST",
        "/api/v1/analyze",
        files={"file": ("sample.txt", b">x\nACGT\n", "text/plain")},
    )
    assert response.status_code == 400


def test_malformed_fasta_fails_closed_instead_of_crashing() -> None:
    response = request(
        "POST",
        "/api/v1/analyze",
        files={"file": ("bad.fasta", b"not-a-fasta\n", "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["qc"]["passed"] is False
    assert all(
        result["final_status"] == "no_call" for result in response.json()["results"]
    )
