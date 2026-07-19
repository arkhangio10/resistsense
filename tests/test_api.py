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
