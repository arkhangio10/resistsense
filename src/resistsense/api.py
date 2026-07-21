from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from .auditor_eval import run_auditor_safety_eval
from .config import load_config
from .evidence_auditor import audit_analysis
from .pipeline import analyze_fasta, runtime_readiness
from .reporter import audit_report
from .schemas import AnalysisResponse
from .verified_demo import verified_demo_payload


def _cors_origins() -> list[str]:
    configured = os.getenv("RESISTSENSE_CORS_ORIGINS")
    if configured:
        return sorted(
            {
                origin.strip().rstrip("/")
                for origin in configured.split(",")
                if origin.strip()
            }
        )
    return [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


app = FastAPI(
    title="ResistSense API",
    version="0.1.0",
    description="Defensive antimicrobial-resistance research prototype",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "resistsense-api"}


@app.get("/api/v1/readiness")
def readiness() -> dict:
    return runtime_readiness()


@app.get("/api/v1/scope")
def scope() -> dict:
    config = load_config()
    return {
        "project": config.project.name,
        "tagline": config.project.tagline,
        "species": config.scope.species.model_dump(),
        "antibiotics": config.scope.antibiotics,
        "disclaimer": config.project.mandatory_disclaimer,
    }


@app.get("/api/v1/verified-demo")
def verified_demo() -> dict:
    payload = verified_demo_payload()
    report = AnalysisResponse.model_validate(payload["analysis"])
    violations = audit_report(report)
    if violations:
        raise HTTPException(
            status_code=500,
            detail={"message": "Verified demo safety audit failed", "violations": violations},
        )
    return payload


@app.get("/api/v1/dataset-audit")
def dataset_audit() -> dict:
    curated_path = Path(
        os.getenv(
            "RESISTSENSE_PHASE2_SUMMARY",
            "artifacts/phase2/curated_cohort_summary.json",
        )
    )
    if curated_path.is_file():
        curated = json.loads(curated_path.read_text(encoding="utf-8"))
        totals: dict[str, dict[str, int]] = {}
        for item in curated["balance"]:
            total = totals.setdefault(
                item["antibiotic"], {"resistant": 0, "susceptible": 0}
            )
            total["resistant"] += item["resistant"]
            total["susceptible"] += item["susceptible"]
        return {
            "status": curated["status"],
            "source": curated["source"],
            "species": curated["species"],
            "unique_genomes": curated["samples"],
            "antibiotics": [
                {
                    "antibiotic": antibiotic,
                    "eligible_pairs": values["resistant"] + values["susceptible"],
                    "susceptible_pairs": values["susceptible"],
                    "resistant_pairs": values["resistant"],
                    "resistant_pct": round(
                        100
                        * values["resistant"]
                        / (values["resistant"] + values["susceptible"]),
                        2,
                    ),
                }
                for antibiotic, values in totals.items()
            ],
            "genetic_clusters": curated["genetic_groups"],
            "preliminary_qc_pass_pct": 100.0,
            "input_sha256": curated["manifest_sha256"],
            "split_counts": curated["split_counts"],
            "curation_version": curated["curation_version"],
        }

    path = Path("artifacts/phase2/phase2_audit.json")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dataset audit artifact unavailable")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": payload["interpretation"]["organizer_dataset_status"],
        "source": payload["source"],
        "species": payload["species"],
        "unique_genomes": payload["unique_genomes_across_selected_antibiotics"],
        "antibiotics": [
            {
                "antibiotic": item["antibiotic"],
                "eligible_pairs": item["eligible_pairs"],
                "susceptible_pairs": item["susceptible_pairs"],
                "resistant_pairs": item["resistant_pairs"],
                "resistant_pct": item["resistant_pct"],
            }
            for item in payload["antibiotics"]
        ],
        "genetic_clusters": payload["genome_metadata"]["cgmlst_hc50"][
            "unique_clusters"
        ],
        "preliminary_qc_pass_pct": payload["genome_metadata"][
            "preliminary_qc_pass_pct"
        ],
        "input_sha256": payload["input_sha256"],
    }


@app.get("/api/v1/prediction-autopsy")
def prediction_autopsy() -> dict:
    path = Path(
        os.getenv(
            "RESISTSENSE_PREDICTION_AUTOPSY",
            "artifacts/evaluation/prediction_autopsy.json",
        )
    )
    if not path.is_file():
        raise HTTPException(
            status_code=404, detail="Prediction Autopsy artifact unavailable"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"status", "source", "selection_policy", "disclaimer", "summary", "cases"}
    missing = required.difference(payload)
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction Autopsy artifact is incomplete: {sorted(missing)}",
        )
    return {name: payload[name] for name in required}


@app.get("/api/v1/safety-report")
def safety_report() -> dict:
    path = Path(
        os.getenv(
            "RESISTSENSE_SAFETY_REPORT",
            "artifacts/evaluation/class_aware_safety_report.json",
        )
    )
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Safety report artifact unavailable")
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "status",
        "research_demo_status",
        "clinical_release_status",
        "clinical_release_reasons",
        "source",
        "predictions_sha256",
        "evaluation_scope",
        "limitations",
        "antibiotics",
    }
    missing = required.difference(payload)
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Safety report artifact is incomplete: {sorted(missing)}",
        )
    return {name: payload[name] for name in required}


@app.get("/api/v1/auditor-safety-eval")
def auditor_safety_eval() -> dict:
    config = load_config()
    report = run_auditor_safety_eval(config.openai_auditor)
    return report.model_dump(mode="json")


@app.get("/api/v1/system-provenance")
def system_provenance() -> dict:
    config = load_config()
    config_path = Path(
        os.getenv("RESISTSENSE_CONFIG", "configs/resistsense.yaml")
    )
    policy_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
    return {
        "schema_version": "1.0",
        "project": config.project.name,
        "mode": config.project.mode,
        "species": config.scope.species.scientific_name,
        "policy": {
            "source": str(config_path).replace("\\", "/"),
            "sha256": policy_sha256,
            "fail_safe": True,
            "resistant_probability_threshold": (
                config.firewall.resistant_probability_threshold
            ),
            "susceptible_probability_threshold": (
                config.firewall.susceptible_probability_threshold
            ),
            "maximum_model_disagreement": (
                config.firewall.maximum_model_disagreement
            ),
            "maximum_ood_score": config.firewall.maximum_ood_score,
        },
        "models": {
            antibiotic: policy.strategy
            for antibiotic, policy in config.modeling.antibiotics.items()
        },
        "auditor": {
            "model": config.openai_auditor.model,
            "prompt_version": config.openai_auditor.prompt_version,
            "structured_output": True,
            "store": False,
            "raw_fasta_sent_to_openai": False,
            "decision_mutation_allowed": False,
        },
        "release_boundary": {
            "research_use_only": True,
            "laboratory_confirmation_required": True,
            "treatment_recommendation_allowed": False,
            "external_validation_complete": False,
        },
    }


@app.post("/api/v1/analyze")
async def analyze(file: UploadFile = File(...)) -> dict:
    config = load_config()
    filename = file.filename or "uploaded.fasta"
    if not filename.lower().endswith((".fa", ".fna", ".fasta")):
        raise HTTPException(status_code=400, detail="Upload a .fa, .fna, or .fasta file")
    content = await file.read(config.runtime.max_upload_bytes + 1)
    if len(content) > config.runtime.max_upload_bytes:
        raise HTTPException(status_code=413, detail="FASTA exceeds the upload limit")
    response = await run_in_threadpool(analyze_fasta, content, filename, config)
    violations = audit_report(response)
    if violations:
        raise HTTPException(
            status_code=500,
            detail={"message": "Report safety audit failed", "violations": violations},
        )
    return response.model_dump(mode="json")


@app.post("/api/v1/evidence-audit")
async def evidence_audit(report: AnalysisResponse) -> dict:
    violations = audit_report(report)
    if violations:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Scientific report failed the deterministic safety audit",
                "violations": violations,
            },
        )
    config = load_config()
    response = await run_in_threadpool(
        audit_analysis, report, config.openai_auditor
    )
    return response.model_dump(mode="json")
