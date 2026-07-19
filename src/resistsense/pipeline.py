from __future__ import annotations

import uuid
from pathlib import Path

from .amrfinder import amrfinder_runtime_available, annotate_fasta
from .config import ResistSenseConfig, load_config
from .fasta import validate_fasta
from .features import feature_mapping, vectorize
from .firewall import DrugEvidence, decide
from .model_store import artifact_name, get_model
from .schemas import AnalysisResponse, AnnotationReport
from .target_annotation import annotate_targets, target_annotator_available
from .targets import evaluate_target, load_target_catalog, relevant_markers


def _not_run(reason: str) -> AnnotationReport:
    return AnnotationReport(available=False, error=reason)


def analyze_fasta(
    content: bytes,
    filename: str,
    config: ResistSenseConfig | None = None,
) -> AnalysisResponse:
    active = config or load_config()
    qc = validate_fasta(content, filename, active.fasta_qc)
    annotation = (
        annotate_fasta(
            content,
            active.scope.species.amrfinderplus_organism,
            active.runtime.amrfinder_timeout_seconds,
        )
        if qc.passed
        else _not_run("AMRFinderPlus was not run because FASTA QC failed")
    )

    targets_path = Path("configs/drug_targets.yaml")
    targets = load_target_catalog(targets_path)
    target_observation = (
        annotate_targets(
            content,
            targets_path,
            active.runtime.target_annotator_timeout_seconds,
        )
        if qc.passed
        else None
    )
    target_symbols = (
        target_observation.gene_symbols
        if target_observation is not None and target_observation.available
        else None
    )
    mapping = feature_mapping(
        annotation.markers,
        qc,
        fasta_content=content if qc.passed else None,
        kmer=active.features.kmer,
    )
    results = []
    model_dir = str(active.runtime.model_dir)

    for antibiotic in active.scope.antibiotics:
        bundle = get_model(model_dir, antibiotic)
        prediction = (
            bundle.predict(vectorize(mapping, bundle.feature_names))
            if bundle is not None and qc.passed and annotation.available
            else None
        )
        target_status, target = evaluate_target(antibiotic, target_symbols, targets)
        evidence = DrugEvidence(
            antibiotic=antibiotic,
            qc=qc,
            annotation_available=annotation.available,
            model_available=bundle is not None,
            calibrated_probability_resistant=(
                prediction.probability_resistant if prediction else None
            ),
            calibrated=prediction is not None,
            conformal_set=prediction.conformal_set if prediction else set(),
            model_probabilities=(
                prediction.model_probabilities if prediction else {}
            ),
            ood_score=prediction.ood_score if prediction else None,
            target_status=target_status,
            target_class=target.target_class if target else None,
            known_markers=relevant_markers(annotation.markers, target),
        )
        results.append(decide(evidence, active.firewall))

    return AnalysisResponse(
        analysis_id=str(uuid.uuid4()),
        species=active.scope.species.scientific_name,
        disclaimer=active.project.mandatory_disclaimer,
        qc=qc,
        annotation=annotation,
        results=results,
    )


def runtime_readiness(config: ResistSenseConfig | None = None) -> dict:
    active = config or load_config()
    models = {
        antibiotic: (Path(active.runtime.model_dir) / artifact_name(antibiotic)).is_file()
        for antibiotic in active.scope.antibiotics
    }
    amrfinderplus = amrfinder_runtime_available()
    target_annotator = target_annotator_available()
    return {
        "project": active.project.name,
        "mode": active.project.mode,
        "species": active.scope.species.scientific_name,
        "antibiotics": active.scope.antibiotics,
        "models": models,
        "amrfinderplus": amrfinderplus,
        "independent_target_annotator": target_annotator,
        "ready_for_probable_failure": all(models.values()) and amrfinderplus,
        "ready_for_probable_efficacy": (
            all(models.values()) and amrfinderplus and target_annotator
        ),
        "ready_for_prediction": (
            all(models.values()) and amrfinderplus and target_annotator
        ),
        "safe_when_incomplete": True,
    }
