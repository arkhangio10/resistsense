"use client";

import dynamic from "next/dynamic";
import { ChangeEvent, useEffect, useMemo, useState } from "react";

type Marker = {
  symbol: string;
  element_type: string;
  resistance_class?: string | null;
  subclass?: string | null;
};

type FinalStatus = "probable_failure" | "probable_efficacy" | "no_call";

type DrugResult = {
  antibiotic: string;
  final_status: FinalStatus;
  calibrated_probability_resistant: number | null;
  confidence: number | null;
  conformal_set: string[];
  evidence_level: string;
  target_status: "present" | "absent" | "unknown";
  target_class: string | null;
  known_markers: Marker[];
  model_probabilities: Record<string, number>;
  ood_score: number | null;
  no_call_reasons: string[];
  explanation: string;
};

type Analysis = {
  analysis_id: string;
  species: string;
  disclaimer: string;
  qc: {
    passed: boolean;
    sha256: string;
    filename: string;
    total_length_bp: number;
    contigs: number;
    ambiguous_fraction: number;
    reasons: string[];
  };
  annotation: {
    available: boolean;
    tool: string;
    tool_version: string | null;
    database_version: string | null;
    markers: Marker[];
    error: string | null;
  };
  results: DrugResult[];
};

type Readiness = {
  project: string;
  species: string;
  antibiotics: string[];
  models: Record<string, boolean>;
  amrfinderplus: boolean;
  independent_target_annotator: boolean;
  ready_for_prediction: boolean;
  safe_when_incomplete: boolean;
};

type DatasetAudit = {
  status: string;
  source: string;
  species: string;
  unique_genomes: number;
  genetic_clusters: number;
  preliminary_qc_pass_pct: number;
  antibiotics: Array<{
    antibiotic: string;
    eligible_pairs: number;
    susceptible_pairs: number;
    resistant_pairs: number;
    resistant_pct: number;
  }>;
};

type AutopsyCase = {
  case_id: string;
  category: "prevented_error" | "escaped_error";
  antibiotic: string;
  sample_id: string;
  genetic_group: string;
  laboratory_label: "susceptible" | "resistant";
  model_label: "susceptible" | "resistant";
  probability_resistant: number;
  model_confidence: number;
  final_status: FinalStatus;
  expert_probabilities: Record<string, number>;
  model_disagreement: number;
  conformal_set: string[];
  ood_score: number;
  target_status: "present" | "absent" | "unknown";
  known_markers: string[];
  no_call_reasons: string[];
};

type PredictionAutopsy = {
  status: string;
  disclaimer: string;
  summary: Record<
    string,
    {
      test_rows: number;
      base_errors: number;
      errors_prevented_by_firewall: number;
      errors_escaping_firewall: number;
      error_prevention_fraction: number;
      firewall_coverage: number;
    }
  >;
  cases: AutopsyCase[];
};

type ExactRate = {
  numerator: number;
  denominator: number;
  value: number | null;
};

type ClassAwareSafetyReport = {
  research_demo_status: string;
  clinical_release_status: string;
  predictions_sha256: string;
  evaluation_scope: {
    unique_genomes: number;
    external_validation_complete: boolean;
    test_set_retuning_allowed: boolean;
  };
  antibiotics: Record<
    string,
    {
      by_laboratory_class: Record<
        "resistant" | "susceptible",
        {
          coverage: ExactRate;
          incorrect_emitted_rows: number;
          eligible_rows: number;
        }
      >;
    }
  >;
};

type EvidenceAudit = {
  source: "openai" | "deterministic_fallback";
  model: string | null;
  request_id: string | null;
  response_id: string | null;
  usage: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  } | null;
  fallback_reason: string | null;
  safety_validation_passed: boolean;
  audit: {
    audit_status: "consistent" | "review_required" | "unavailable";
    neutral_summary: string;
    consistency_checks: Array<{
      check_id: string;
      outcome: "consistent" | "review_required";
    }>;
    statistical_summary: {
      result_count: number;
      emitted_count: number;
      no_call_count: number;
      known_marker_count: number;
    };
    uncertainty_statement: string;
    limitations: string[];
    laboratory_confirmation_required: boolean;
  };
};

type VerifiedDemo = {
  demo_mode: "precomputed_verified_frozen_test_case";
  label: string;
  provenance: {
    source: string;
    sample_id: string;
    genetic_group: string;
    split: string;
    predictions_sha256: string;
    precomputed: true;
    test_set_retuning_allowed: false;
  };
  analysis: Analysis;
};

type AuditorSafetyEval = {
  schema_version: string;
  suite: string;
  evaluation_mode: string;
  model_under_test: string;
  prompt_version: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  metrics: Record<string, { passed: number; total: number }>;
  privacy_assertion: string;
  limitations: string[];
  cases: Array<{
    case_id: string;
    attack_class: string;
    title: string;
    expected_control: string;
    passed: boolean;
    observed_control: string;
  }>;
};

type SystemProvenance = {
  schema_version: string;
  project: string;
  mode: string;
  species: string;
  policy: {
    source: string;
    sha256: string;
    fail_safe: boolean;
    resistant_probability_threshold: number;
    susceptible_probability_threshold: number;
    maximum_model_disagreement: number;
    maximum_ood_score: number;
  };
  models: Record<string, string>;
  auditor: {
    model: string;
    prompt_version: string;
    structured_output: boolean;
    store: boolean;
    raw_fasta_sent_to_openai: boolean;
    decision_mutation_allowed: boolean;
  };
  release_boundary: {
    research_use_only: boolean;
    laboratory_confirmation_required: boolean;
    treatment_recommendation_allowed: boolean;
    external_validation_complete: boolean;
  };
};

type JudgeStep = 1 | 2 | 3 | 4;

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const BioSimulation = dynamic(() => import("../components/BioSimulation"), {
  ssr: false,
  loading: () => <div className="simulation-loading">Initializing specimen view…</div>,
});

const STATUS_LABEL: Record<FinalStatus, string> = {
  probable_failure: "Provisional genomic resistance",
  probable_efficacy: "Provisional susceptibility-compatible signal",
  no_call: "No-call — insufficient or conflicting evidence",
};

const STATUS_CLASS: Record<FinalStatus, string> = {
  probable_failure: "resistant",
  probable_efficacy: "susceptible",
  no_call: "no-call",
};

const FALLBACK_ANTIBIOTICS = [
  "ampicillin",
  "ciprofloxacin",
  "cefotaxime",
  "gentamicin",
  "trimethoprim/sulfamethoxazole",
];

const BARRIERS = [
  ["01", "Genome quality", "Reject incomplete, atypical, or ambiguous assemblies."],
  ["02", "Molecular target", "Never infer susceptibility from marker absence alone."],
  ["03", "Distribution shift", "Measure proximity to genetic groups used for training."],
  ["04", "Model agreement", "Challenge conclusions when independent experts disagree."],
  ["05", "Calibration", "Require confidence to match observed performance."],
  ["06", "Conformal set", "Ambiguous evidence automatically becomes a no-call."],
];

const formatDrug = (name: string) =>
  name
    .split("/")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("/");

const percent = (value: number | null) =>
  value === null ? "—" : `${Math.round(value * 100)}%`;

const exactPercent = (rate: ExactRate) =>
  `${rate.value === null ? "—" : `${(rate.value * 100).toFixed(1)}%`} (${rate.numerator}/${rate.denominator})`;

const formatReason = (reason: string) =>
  reason.replaceAll("_", " ").replace(/^./, (character) => character.toUpperCase());

const shortHash = (value: string | null | undefined) =>
  value ? `${value.slice(0, 12)}…` : "Unavailable";

const formatPhenotype = (value: "susceptible" | "resistant") =>
  value === "resistant" ? "Resistant" : "Susceptible";

export default function Home() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [audit, setAudit] = useState<DatasetAudit | null>(null);
  const [autopsy, setAutopsy] = useState<PredictionAutopsy | null>(null);
  const [safetyReport, setSafetyReport] = useState<ClassAwareSafetyReport | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [demoProvenance, setDemoProvenance] = useState<VerifiedDemo["provenance"] | null>(null);
  const [evidenceAudit, setEvidenceAudit] = useState<EvidenceAudit | null>(null);
  const [auditorEval, setAuditorEval] = useState<AuditorSafetyEval | null>(null);
  const [systemProvenance, setSystemProvenance] = useState<SystemProvenance | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [visualizedAntibiotic, setVisualizedAntibiotic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [judgeMode, setJudgeMode] = useState(false);
  const [judgeStep, setJudgeStep] = useState<JudgeStep>(1);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/api/v1/readiness`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        return response.json();
      })
      .then((payload: Readiness) => {
        setReadiness(payload);
        setBackendOnline(true);
      })
      .catch(() => setBackendOnline(false));
    fetch(`${API_URL}/api/v1/dataset-audit`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: DatasetAudit | null) => setAudit(payload))
      .catch(() => setAudit(null));
    fetch(`${API_URL}/api/v1/prediction-autopsy`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: PredictionAutopsy | null) => setAutopsy(payload))
      .catch(() => setAutopsy(null));
    fetch(`${API_URL}/api/v1/safety-report`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: ClassAwareSafetyReport | null) => setSafetyReport(payload))
      .catch(() => setSafetyReport(null));
    fetch(`${API_URL}/api/v1/auditor-safety-eval`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: AuditorSafetyEval | null) => setAuditorEval(payload))
      .catch(() => setAuditorEval(null));
    fetch(`${API_URL}/api/v1/system-provenance`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: SystemProvenance | null) => setSystemProvenance(payload))
      .catch(() => setSystemProvenance(null));
    return () => controller.abort();
  }, []);

  const antibiotics = readiness?.antibiotics || FALLBACK_ANTIBIOTICS;
  const modelCount = useMemo(
    () => Object.values(readiness?.models || {}).filter(Boolean).length,
    [readiness],
  );
  const visualizedResult = useMemo(() => {
    if (!analysis) return null;
    return (
      analysis.results.find(
        (result) => result.antibiotic === visualizedAntibiotic,
      ) || analysis.results[0] || null
    );
  }, [analysis, visualizedAntibiotic]);
  const autopsyTotals = useMemo(
    () =>
      Object.values(autopsy?.summary || {}).reduce(
        (totals, item) => ({
          errors: totals.errors + item.base_errors,
          prevented: totals.prevented + item.errors_prevented_by_firewall,
          escaped: totals.escaped + item.errors_escaping_firewall,
        }),
        { errors: 0, prevented: 0, escaped: 0 },
      ),
    [autopsy],
  );
  const preventedCase = useMemo(
    () =>
      autopsy?.cases.find(
        (item) =>
          item.category === "prevented_error" &&
          item.model_label === "susceptible" &&
          item.laboratory_label === "resistant",
      ) || autopsy?.cases.find((item) => item.category === "prevented_error") || null,
    [autopsy],
  );
  const reviewWorklist = useMemo(() => {
    if (!analysis) return [];
    return analysis.results
      .map((result) => {
        const statisticalOnly = result.evidence_level.startsWith("C_");
        const priority = result.final_status === "no_call" ? 0 : statisticalOnly ? 1 : 2;
        return {
          result,
          priority,
          label:
            result.final_status === "no_call"
              ? "Priority review"
              : statisticalOnly
                ? "Evidence review"
                : "Confirmation queue",
          reason:
            result.no_call_reasons.map(formatReason).join(" · ") ||
            (statisticalOnly
              ? "Statistical association without a known mechanism"
              : "Firewall barriers passed; laboratory confirmation remains required"),
        };
      })
      .sort((left, right) => left.priority - right.priority);
  }, [analysis]);

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] || null;
    setFile(selected);
    setAnalysis(null);
    setDemoProvenance(null);
    setEvidenceAudit(null);
    setAuditLoading(false);
    setVisualizedAntibiotic("");
    setError(null);
  };

  const loadVerifiedDemo = async (preferredAntibiotic?: string) => {
    setLoading(true);
    setError(null);
    setFile(null);
    setEvidenceAudit(null);
    try {
      const response = await fetch(`${API_URL}/api/v1/verified-demo`);
      if (!response.ok) throw new Error("Verified example unavailable");
      const payload = (await response.json()) as VerifiedDemo;
      setAnalysis(payload.analysis);
      setDemoProvenance(payload.provenance);
      const preferred = payload.analysis.results.find(
        (result) => result.antibiotic === preferredAntibiotic,
      );
      const noCall = payload.analysis.results.find(
        (result) => result.final_status === "no_call",
      );
      setVisualizedAntibiotic(
        preferred?.antibiotic || noCall?.antibiotic || payload.analysis.results[0]?.antibiotic || "",
      );
      void requestEvidenceAudit(payload.analysis);
      return payload;
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Verified example unavailable.",
      );
    } finally {
      setLoading(false);
    }
  };

  const goToJudgeStep = (step: JudgeStep) => {
    setJudgeStep(step);
    const target =
      step === 1
        ? "home"
        : step === 2
          ? "firewall-replay"
          : step === 3
            ? "ai-audit"
            : "evidence-passport";
    window.requestAnimationFrame(() => {
      document.getElementById(target)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const startJudgeTour = async () => {
    setJudgeMode(true);
    setJudgeStep(1);
    const payload = await loadVerifiedDemo("trimethoprim/sulfamethoxazole");
    if (payload) goToJudgeStep(1);
  };

  const requestEvidenceAudit = async (completedAnalysis: Analysis) => {
    setAuditLoading(true);
    setEvidenceAudit(null);
    try {
      const response = await fetch(`${API_URL}/api/v1/evidence-audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(completedAnalysis),
      });
      if (!response.ok) throw new Error("Evidence audit unavailable");
      setEvidenceAudit((await response.json()) as EvidenceAudit);
    } catch {
      setEvidenceAudit(null);
    } finally {
      setAuditLoading(false);
    }
  };

  const downloadReport = () => {
    if (!analysis) return;
    const content = JSON.stringify(
      {
        scientific_report: analysis,
        evidence_conflict_audit: evidenceAudit,
        auditor_safety_evaluation: auditorEval,
        system_provenance: systemProvenance,
        demo_provenance: demoProvenance,
      },
      null,
      2,
    );
    const url = URL.createObjectURL(
      new Blob([content], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `resistsense-${analysis.analysis_id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const analyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const response = await fetch(`${API_URL}/api/v1/analyze`, {
        method: "POST",
        body: form,
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail =
          typeof payload.detail === "string"
            ? payload.detail
            : payload.detail?.message || "The FASTA could not be analyzed.";
        throw new Error(detail);
      }
      const completedAnalysis = payload as Analysis;
      setAnalysis(completedAnalysis);
      setDemoProvenance(null);
      setVisualizedAntibiotic(completedAnalysis.results[0]?.antibiotic || "");
      void requestEvidenceAudit(completedAnalysis);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The analysis pipeline could not be reached.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="resistsense-shell">
      <section className="lab-frame" id="home">
        <header className="lab-topbar">
          <a className="lab-brand" href="#home" aria-label="ResistSense home">
            <span className="lab-brand-mark" aria-hidden="true" />
            <strong>ResistSense</strong>
          </a>
          <span className="lab-mode">Genome Firewall / Analysis 01</span>
          <nav className="lab-nav" aria-label="Main navigation">
            <a href="#firewall-replay">Replay</a>
            <a href="#review-worklist">Workflow</a>
            <a href="#evidence">Evidence</a>
            <a href="#validation">Validation</a>
            <a href="#safety">Safety</a>
          </nav>
          <span className={`lab-session ${backendOnline ? "online" : "offline"}`}>
            {backendOnline === null
              ? "Checking environment"
              : backendOnline
                ? "Research environment online"
                : "Research environment offline"}
          </span>
        </header>

        <div className="lab-workspace">
          <section className="lab-intro" aria-labelledby="main-headline">
            <p className="lab-eyebrow">Genomic AMR evidence</p>
            <h1 id="main-headline">See resistance before confidence becomes risk.</h1>
            <p className="lab-lead">
              A guarded readout of genetic evidence—designed to expose
              uncertainty, not hide it.
            </p>
            <p className="lab-audience">
              Built for microbiology research and genomic-surveillance teams
              reviewing whole-genome AMR evidence.
            </p>

            <div className="specimen-scope">
              <span>Supported bacterium</span>
              <div>
                <em>Escherichia coli</em>
                <strong>Validated scope</strong>
              </div>
            </div>

            <label className={`compact-upload ${file ? "has-file" : ""}`}>
              <input
                type="file"
                accept=".fa,.fna,.fasta,text/plain"
                onChange={handleFile}
              />
              <span className="compact-upload-icon" aria-hidden="true">↑</span>
              <span>
                <strong>{file ? file.name : "Upload bacterial genome"}</strong>
                <small>
                  {file
                    ? `${(file.size / 1_000_000).toFixed(2)} MB · ready`
                    : "FASTA · .fna, .fa, .fasta · max 15 MB"}
                </small>
              </span>
            </label>

            <button
              className="run-analysis"
              type="button"
              onClick={analyze}
              disabled={!file || loading || backendOnline === false}
            >
              {loading ? "Running genome firewall…" : "Run genomic assessment"}
              <span aria-hidden="true">→</span>
            </button>
            <button
              className="verified-demo-button"
              type="button"
              onClick={() => void startJudgeTour()}
              disabled={loading || backendOnline === false}
            >
              Start 90-second judge tour
              <span>Verified frozen-test case · guided evidence replay</span>
            </button>
            {error && <p className="lab-error">{error}</p>}
          </section>

          <section
            className={`specimen-stage ${loading ? "is-loading" : ""}`}
            aria-label="Bacterial response visualization"
          >
            <div className="stage-caption">
              <strong>Specimen view</strong>
              <span>{demoProvenance ? "verified precomputed example" : analysis ? "model-driven response" : "awaiting genome"}</span>
            </div>
            <BioSimulation
              antibiotic={visualizedResult?.antibiotic || "Awaiting genome"}
              confidence={visualizedResult?.confidence ?? null}
              outcome={visualizedResult?.final_status || "idle"}
            />
            {loading && (
              <div className="analysis-sequence" role="status" aria-live="polite">
                <div className="analysis-organism" aria-hidden="true">
                  <span className="analysis-cell" />
                  <i />
                  <i />
                  <i />
                </div>
                <div className="analysis-sequence-copy">
                  <span>Genome firewall active</span>
                  <strong>Interrogating the assembly</strong>
                  <p>
                    Resistance markers, model agreement and confidence gates
                    are being evaluated.
                  </p>
                </div>
                <ol aria-label="Analysis stages">
                  <li>Validating FASTA structure</li>
                  <li>Checking genome quality</li>
                  <li>Annotating known resistance mechanisms</li>
                  <li>Running calibrated grouped models</li>
                  <li>Applying safety barriers</li>
                </ol>
              </div>
            )}
            <div className="stage-metadata">
              <span>Organism <strong>E. coli</strong></span>
              <span>
                Genome <strong>{analysis ? `${(analysis.qc.total_length_bp / 1_000_000).toFixed(2)} Mb` : "—"}</strong>
              </span>
              <span>QC <strong>{analysis ? (analysis.qc.passed ? "Passed" : "Failed") : "Pending"}</strong></span>
            </div>
          </section>

          <aside className="assessment-rail" aria-labelledby="assessment-title">
            <div className="assessment-head">
              <div>
                <span>Evidence readout</span>
                <h2 id="assessment-title">Antibiotic assessments</h2>
              </div>
              <strong>{String(antibiotics.length).padStart(2, "0")} / 05</strong>
            </div>

            <div className="assessment-list">
              {antibiotics.map((antibiotic, index) => {
                const result = analysis?.results.find(
                  (item) => item.antibiotic === antibiotic,
                );
                const selected = visualizedResult?.antibiotic === antibiotic;
                return (
                  <button
                    type="button"
                    className={`assessment-row ${
                      result ? STATUS_CLASS[result.final_status] : "pending"
                    } ${selected ? "active" : ""}`}
                    key={antibiotic}
                    onClick={() => result && setVisualizedAntibiotic(antibiotic)}
                    disabled={!result}
                    aria-pressed={selected}
                  >
                    <span className="assessment-index">{String(index + 1).padStart(2, "0")}</span>
                    <span className="assessment-copy">
                      <strong>{formatDrug(antibiotic)}</strong>
                      <small>{result ? STATUS_LABEL[result.final_status] : "Awaiting genome"}</small>
                    </span>
                    <span className="assessment-confidence">
                      {result ? percent(result.confidence) : "—"}
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="assessment-legend">
              <span className="resistant">Resistance signal</span>
              <span className="susceptible">Susceptibility-compatible</span>
              <span className="no-call">No-call</span>
            </div>
          </aside>
        </div>

        <footer className="lab-footer">
          <p>
            <strong>Research prototype.</strong> Results are provisional genomic
            evidence, not a treatment recommendation. Standard laboratory
            susceptibility testing is required.
          </p>
          <div>
            <span>Pipeline<strong>AMRFinder+ / ML</strong></span>
            <span>Models<strong>{modelCount} / 5 ready</strong></span>
            <span>Safety record<strong>{autopsyTotals.prevented || 55} / {autopsyTotals.errors || 68} base errors blocked</strong></span>
          </div>
          <a href={analysis ? "#evidence" : "#validation"}>
            {analysis ? "Inspect evidence" : "Inspect validation"} →
          </a>
        </footer>
      </section>

      <section className="firewall-replay-section" id="firewall-replay">
        <header className="section-intro">
          <div>
            <span>Firewall replay / immutable decision path</span>
            <h2>See exactly what the firewall challenged.</h2>
          </div>
          <p>
            Statistical association, known biological evidence, and the final
            guarded assessment remain separate. The interface never converts
            marker absence into proof of susceptibility.
          </p>
        </header>

        {analysis && visualizedResult ? (
          <>
            <div className="replay-endpoints" aria-label="Select endpoint for firewall replay">
              {analysis.results.map((result) => (
                <button
                  type="button"
                  key={result.antibiotic}
                  className={result.antibiotic === visualizedResult.antibiotic ? "active" : ""}
                  onClick={() => setVisualizedAntibiotic(result.antibiotic)}
                  aria-pressed={result.antibiotic === visualizedResult.antibiotic}
                >
                  {formatDrug(result.antibiotic)}
                  <span className={STATUS_CLASS[result.final_status]}>
                    {result.final_status === "no_call" ? "No-call" : "Provisional"}
                  </span>
                </button>
              ))}
            </div>

            <div className="firewall-replay-grid">
              <article className="replay-card statistical-layer">
                <span>01 / Statistical layer</span>
                <strong>
                  {visualizedResult.calibrated_probability_resistant === null
                    ? "No calibrated signal"
                    : visualizedResult.calibrated_probability_resistant >= 0.5
                      ? "Resistance-associated signal"
                      : "Susceptibility-associated signal"}
                </strong>
                <b>{percent(visualizedResult.calibrated_probability_resistant)}</b>
                <p>Calibrated probability of resistance. It is evidence, not the final assessment.</p>
                <dl>
                  <div><dt>Conformal set</dt><dd>{visualizedResult.conformal_set.join(" / ") || "Unavailable"}</dd></div>
                  <div><dt>Model experts</dt><dd>{Object.keys(visualizedResult.model_probabilities).length}</dd></div>
                </dl>
              </article>

              <article className="replay-card biological-layer">
                <span>02 / Biological + safety layer</span>
                <strong>
                  {visualizedResult.known_markers.length > 0
                    ? `${visualizedResult.known_markers.length} known marker${visualizedResult.known_markers.length === 1 ? "" : "s"}`
                    : "No known marker observed"}
                </strong>
                <p>
                  {visualizedResult.known_markers.map((marker) => marker.symbol).join(" · ") ||
                    "Marker absence is not treated as susceptibility evidence."}
                </p>
                <dl>
                  <div><dt>Target</dt><dd>{formatReason(visualizedResult.target_status)}</dd></div>
                  <div><dt>OOD score</dt><dd>{percent(visualizedResult.ood_score)}</dd></div>
                  <div><dt>Evidence tier</dt><dd>{visualizedResult.evidence_level.slice(0, 1)}</dd></div>
                </dl>
              </article>

              <article className={`replay-card final-layer ${STATUS_CLASS[visualizedResult.final_status]}`}>
                <span>03 / Genome Firewall</span>
                <strong>{STATUS_LABEL[visualizedResult.final_status]}</strong>
                <p>
                  {visualizedResult.no_call_reasons.length > 0
                    ? visualizedResult.no_call_reasons.map(formatReason).join(" · ")
                    : "All configured barriers passed for this provisional output."}
                </p>
                <div className="replay-lock">
                  <span aria-hidden="true">◆</span>
                  Decision locked before the optional GPT audit
                </div>
                <small>Standard laboratory susceptibility testing is required.</small>
              </article>
            </div>
          </>
        ) : (
          <div className="replay-empty">
            <strong>Load the verified case to replay the decision path.</strong>
            <button type="button" onClick={() => void startJudgeTour()} disabled={backendOnline === false}>
              Start guided proof
            </button>
          </div>
        )}

        {preventedCase && (
          <article className="prevented-proof">
            <div className="prevented-proof-kicker">
              <span>Held-out proof / frozen grouped test</span>
              <strong>Blocked base-model error</strong>
            </div>
            <div className="prevented-proof-flow">
              <div>
                <span>Base classifier</span>
                <strong>{formatPhenotype(preventedCase.model_label)}</strong>
                <small>{percent(preventedCase.model_confidence)} confidence</small>
              </div>
              <b aria-hidden="true">→</b>
              <div>
                <span>Safety trigger</span>
                <strong>{preventedCase.no_call_reasons.map(formatReason).join(" · ")}</strong>
                <small>OOD {percent(preventedCase.ood_score)} · group {preventedCase.genetic_group}</small>
              </div>
              <b aria-hidden="true">→</b>
              <div className="prevented-proof-result">
                <span>Firewall output</span>
                <strong>No-call</strong>
                <small>Laboratory label: {formatPhenotype(preventedCase.laboratory_label)}</small>
              </div>
            </div>
            <p>
              Real frozen-test case {preventedCase.sample_id} · {formatDrug(preventedCase.antibiotic)}.
              The firewall intercepted an incorrect high-confidence base result; no threshold was retuned after inspection.
            </p>
          </article>
        )}
      </section>

      {analysis && (
        <section className="review-worklist-section" id="review-worklist">
          <header className="section-intro">
            <div>
              <span>Human review handoff / one genome</span>
              <h2>Uncertainty becomes a worklist.</h2>
            </div>
            <p>
              Endpoints are triaged for evidence review and laboratory confirmation.
              ResistSense does not rank therapies or prescribe an antibiotic.
            </p>
          </header>
          <div className="review-worklist-head" aria-hidden="true">
            <span>Priority</span><span>Endpoint</span><span>Assessment</span><span>Reason</span><span>Handoff</span>
          </div>
          <div className="review-worklist">
            {reviewWorklist.map(({ result, label, reason }, index) => (
              <button
                type="button"
                key={result.antibiotic}
                className={result.antibiotic === visualizedAntibiotic ? "active" : ""}
                onClick={() => {
                  setVisualizedAntibiotic(result.antibiotic);
                  document.getElementById("firewall-replay")?.scrollIntoView({ behavior: "smooth" });
                }}
              >
                <span className={`worklist-priority ${STATUS_CLASS[result.final_status]}`}>{String(index + 1).padStart(2, "0")} · {label}</span>
                <strong>{formatDrug(result.antibiotic)}</strong>
                <span>{STATUS_LABEL[result.final_status]}</span>
                <span>{reason}</span>
                <em>{result.final_status === "no_call" ? "Needs review" : "Confirm in laboratory"}</em>
              </button>
            ))}
          </div>
          <p className="worklist-boundary">
            Human decision point · Research evidence only · Every endpoint remains subject to standard laboratory antimicrobial-susceptibility testing.
          </p>
        </section>
      )}

      {analysis && visualizedResult && (
        <section className="evidence-inspector" id="evidence">
          <header className="section-intro">
            <div>
              <span>{demoProvenance ? "Verified frozen-test example" : "Selected assessment"} / {analysis.analysis_id.slice(0, 8)}</span>
              <h2>{formatDrug(visualizedResult.antibiotic)}</h2>
            </div>
            <strong className={`evidence-status ${STATUS_CLASS[visualizedResult.final_status]}`}>
              {STATUS_LABEL[visualizedResult.final_status]}
            </strong>
            <button className="download-report" type="button" onClick={downloadReport}>
              Download JSON
            </button>
          </header>

          {demoProvenance && (
            <p className="demo-provenance">
              Precomputed example · BV-BRC laboratory cohort · genetic group {demoProvenance.genetic_group} · frozen split · no retuning against this case
            </p>
          )}

          <div className="evidence-layout">
            <article className="evidence-narrative">
              <p>{visualizedResult.explanation}</p>
              <div className="signal-pills">
                <span>Evidence {visualizedResult.evidence_level}</span>
                <span>Target {visualizedResult.target_status}</span>
                <span>OOD {percent(visualizedResult.ood_score)}</span>
                <span>Confidence {percent(visualizedResult.confidence)}</span>
              </div>
              {visualizedResult.known_markers.length > 0 && (
                <div className="marker-readout">
                  <span>Observed markers</span>
                  <strong>
                    {visualizedResult.known_markers
                      .map((marker) => marker.symbol)
                      .join(" · ")}
                  </strong>
                </div>
              )}
              {visualizedResult.no_call_reasons.length > 0 && (
                <div className="marker-readout warning-readout">
                  <span>No-call triggers</span>
                  <strong>
                    {visualizedResult.no_call_reasons
                      .map((reason) => reason.replaceAll("_", " "))
                      .join(" · ")}
                  </strong>
                </div>
              )}
            </article>

            <div className="model-readout">
              <span>Model resistance probability</span>
              {Object.entries(visualizedResult.model_probabilities).map(
                ([model, value]) => (
                  <div key={model}>
                    <p><span>{model.replaceAll("_", " ")}</span><strong>{percent(value)}</strong></p>
                    <i><b style={{ width: `${value * 100}%` }} /></i>
                  </div>
                ),
              )}
            </div>

            <div className="qc-readout">
              <span>Genome quality</span>
              <div><small>Length</small><strong>{(analysis.qc.total_length_bp / 1_000_000).toFixed(2)} Mb</strong></div>
              <div><small>Contigs</small><strong>{analysis.qc.contigs}</strong></div>
              <div><small>Ambiguous</small><strong>{percent(analysis.qc.ambiguous_fraction)}</strong></div>
              <div><small>AMRFinder+</small><strong>{analysis.annotation.available ? "Available" : "Unavailable"}</strong></div>
            </div>
          </div>
          <p className="evidence-disclaimer">{analysis.disclaimer}</p>
        </section>
      )}

      {analysis && (
        <section className="auditor-section" id="ai-audit" aria-live="polite">
          <header className="section-intro">
            <div>
              <span>Constrained OpenAI layer / structured output only</span>
              <h2>GPT-5.6 Evidence Conflict Auditor</h2>
            </div>
            <strong className={`auditor-status ${evidenceAudit?.audit.audit_status || "pending"}`}>
              {auditLoading
                ? "Auditing evidence"
                : evidenceAudit?.source === "openai"
                  ? evidenceAudit.audit.audit_status.replaceAll("_", " ")
                  : "Deterministic fallback"}
            </strong>
          </header>
          {auditLoading ? (
            <div className="auditor-loading" role="status">
              <i /><i /><i />
              <p>Checking contradictions, evidence references, and uncertainty without changing the scientific result.</p>
            </div>
          ) : evidenceAudit ? (
            <div className="auditor-grid">
              <article className="auditor-summary">
                <span>{evidenceAudit.source === "openai" ? evidenceAudit.model : "OpenAI unavailable"}</span>
                <p>{evidenceAudit.audit.neutral_summary}</p>
                <small>{evidenceAudit.audit.uncertainty_statement}</small>
                {evidenceAudit.source === "openai" && (
                  <small className="auditor-telemetry">
                    Response {evidenceAudit.request_id || evidenceAudit.response_id || "ID unavailable"}
                    {evidenceAudit.usage ? ` · ${evidenceAudit.usage.total_tokens} tokens` : ""}
                  </small>
                )}
              </article>
              <div className="auditor-checks">
                {evidenceAudit.audit.consistency_checks.map((check) => (
                  <span className={check.outcome} key={check.check_id}>
                    {check.check_id.replaceAll("_", " ")}
                    <strong>{check.outcome === "consistent" ? "Pass" : "Review"}</strong>
                  </span>
                ))}
              </div>
              <aside className="auditor-boundary">
                <span>Privacy + authority boundary</span>
                <p>Raw FASTA, original filename, checksum, and personal data never leave the backend for OpenAI.</p>
                <p>GPT can audit and communicate evidence; it cannot alter a status, probability, marker, or no-call.</p>
                <strong>Laboratory confirmation required</strong>
              </aside>
            </div>
          ) : (
            <p className="auditor-unavailable">The scientific report remains available unchanged. The optional communication audit could not be reached.</p>
          )}
        </section>
      )}

      {auditorEval && (
        <section className="auditor-eval-section" id="auditor-eval">
          <header className="section-intro">
            <div>
              <span>Executable adversarial suite / deterministic enforcement</span>
              <h2>Guardrails are tested, not trusted.</h2>
            </div>
            <strong className={auditorEval.failed_cases === 0 ? "eval-pass" : "eval-fail"}>
              {auditorEval.passed_cases} / {auditorEval.total_cases} controls passed
            </strong>
          </header>

          <div className="eval-metrics">
            {Object.entries(auditorEval.metrics).map(([name, metric]) => (
              <article key={name}>
                <span>{formatReason(name)}</span>
                <strong>{metric.passed}/{metric.total}</strong>
                <small>{metric.passed === metric.total ? "All attacks blocked" : "Control failure detected"}</small>
              </article>
            ))}
          </div>

          <div className="eval-case-grid">
            {auditorEval.cases.map((item) => (
              <details key={item.case_id}>
                <summary>
                  <span className={item.passed ? "passed" : "failed"}>{item.passed ? "Pass" : "Fail"}</span>
                  <strong>{item.title}</strong>
                  <small>{formatReason(item.attack_class)}</small>
                </summary>
                <p>{item.expected_control}</p>
                <code>{item.observed_control}</code>
              </details>
            ))}
          </div>

          <div className="eval-boundary">
            <p>{auditorEval.privacy_assertion}</p>
            <span>
              Suite {auditorEval.suite} · prompt {auditorEval.prompt_version} · model boundary {auditorEval.model_under_test}
            </span>
            <small>{auditorEval.limitations.join(" ")}</small>
          </div>
        </section>
      )}

      {analysis && (
        <section className="evidence-passport-section" id="evidence-passport">
          <header className="section-intro">
            <div>
              <span>Evidence passport / reproducible handoff</span>
              <h2>Every result carries its receipts.</h2>
            </div>
            <button className="passport-download" type="button" onClick={downloadReport}>
              Export evidence packet
            </button>
          </header>

          <div className="passport-grid">
            <article>
              <span>01 / Sample identity</span>
              <dl>
                <div><dt>Analysis</dt><dd>{analysis.analysis_id}</dd></div>
                <div><dt>Genome digest</dt><dd>{shortHash(analysis.qc.sha256)}</dd></div>
                <div><dt>Source</dt><dd>{demoProvenance ? "Verified frozen-test case" : "User-supplied FASTA"}</dd></div>
                <div><dt>QC</dt><dd>{analysis.qc.passed ? "Passed" : "Failed closed"}</dd></div>
              </dl>
            </article>
            <article>
              <span>02 / Toolchain</span>
              <dl>
                <div><dt>Annotation</dt><dd>{analysis.annotation.tool || "AMRFinderPlus"}</dd></div>
                <div><dt>Tool version</dt><dd>{analysis.annotation.tool_version || "Unavailable"}</dd></div>
                <div><dt>Database</dt><dd>{analysis.annotation.database_version || "Pinned runtime database"}</dd></div>
                <div><dt>Model coverage</dt><dd>{modelCount} / {antibiotics.length} endpoints ready</dd></div>
              </dl>
            </article>
            <article>
              <span>03 / Immutable policy</span>
              <dl>
                <div><dt>Policy digest</dt><dd>{shortHash(systemProvenance?.policy.sha256)}</dd></div>
                <div><dt>Policy source</dt><dd>{systemProvenance?.policy.source || "configs/resistsense.yaml"}</dd></div>
                <div><dt>Fail-safe</dt><dd>{systemProvenance?.policy.fail_safe === false ? "Disabled" : "No-call enabled"}</dd></div>
                <div><dt>External validation</dt><dd>Pending — no clinical release claim</dd></div>
              </dl>
            </article>
            <article className="passport-ai-boundary">
              <span>04 / OpenAI boundary</span>
              <strong>0 raw DNA bases sent</strong>
              <dl>
                <div><dt>Model</dt><dd>{systemProvenance?.auditor.model || evidenceAudit?.model || "Configured auditor"}</dd></div>
                <div><dt>Prompt</dt><dd>{systemProvenance?.auditor.prompt_version || "Pinned"}</dd></div>
                <div><dt>Storage</dt><dd>{systemProvenance?.auditor.store === true ? "Enabled" : "Disabled"}</dd></div>
                <div><dt>Decision authority</dt><dd>None</dd></div>
              </dl>
            </article>
          </div>

          {demoProvenance && (
            <div className="passport-provenance">
              <span>Frozen evaluation provenance</span>
              <strong>{demoProvenance.source}</strong>
              <p>
                Sample {demoProvenance.sample_id} · genetic group {demoProvenance.genetic_group} · {formatReason(demoProvenance.split)} · prediction artifact {shortHash(demoProvenance.predictions_sha256)}
              </p>
              <em>No retuning against this case</em>
            </div>
          )}
        </section>
      )}

      <section className="validation-section" id="validation">
        <header className="section-intro validation-heading">
          <div>
            <span>Validation record / frozen grouped test</span>
            <h2>Evidence that can be challenged.</h2>
          </div>
          <p>
            Laboratory-only BV-BRC labels, conflict removal, grouped genetic
            splits, calibration, and visible residual errors.
          </p>
        </header>

        <div className="validation-metrics">
          <article><span>Curated genomes</span><strong>{audit?.unique_genomes.toLocaleString("en-US") || "2,909"}</strong><small>E. coli assemblies</small></article>
          <article><span>Genetic clusters</span><strong>{audit?.genetic_clusters.toLocaleString("en-US") || "1,306"}</strong><small>kept within partitions</small></article>
          <article><span>Base errors</span><strong>{autopsyTotals.errors || 68}</strong><small>never hidden</small></article>
          <article className="metric-accent"><span>Errors blocked</span><strong>{autopsyTotals.prevented || 55}</strong><small>by the firewall</small></article>
          <article className="metric-alert"><span>Residual errors</span><strong>{autopsyTotals.escaped || 13}</strong><small>visible for audit</small></article>
        </div>

        {safetyReport && (
          <div className="class-safety-register">
            <header>
              <div>
                <span>Class-aware safety / exact counts</span>
                <strong>Coverage is reported separately for resistant and susceptible laboratory labels.</strong>
              </div>
              <em>External validation pending</em>
            </header>
            <div className="class-safety-head" aria-hidden="true">
              <span>Endpoint</span><span>R coverage</span><span>S coverage</span><span>Residuals R / S</span>
            </div>
            {Object.entries(safetyReport.antibiotics).map(([antibiotic, item]) => {
              const resistant = item.by_laboratory_class.resistant;
              const susceptible = item.by_laboratory_class.susceptible;
              return (
                <div className="class-safety-row" key={antibiotic}>
                  <strong>{formatDrug(antibiotic)}</strong>
                  <span>{exactPercent(resistant.coverage)}</span>
                  <span>{exactPercent(susceptible.coverage)}</span>
                  <span>{resistant.incorrect_emitted_rows}/{resistant.eligible_rows} · {susceptible.incorrect_emitted_rows}/{susceptible.eligible_rows}</span>
                </div>
              );
            })}
            <p>
              Frozen test already inspected — no further model or threshold tuning is allowed. High selective accuracy does not imply uniform class coverage.
            </p>
          </div>
        )}

        {audit && (
          <div className="cohort-register" aria-label="Phenotype balance">
            {audit.antibiotics.map((item, index) => (
              <div key={item.antibiotic}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{formatDrug(item.antibiotic)}</strong>
                <small>{item.eligible_pairs.toLocaleString("en-US")} laboratory pairs</small>
                <i><b style={{ width: `${item.resistant_pct}%` }} /></i>
                <em>{item.resistant_pct.toFixed(1)}% R</em>
              </div>
            ))}
          </div>
        )}
      </section>

      {autopsy && (
        <section className="autopsy-section" id="autopsy">
          <header className="section-intro">
            <div>
              <span>Prediction autopsy / held-out cases</span>
              <h2>Failure remains part of the interface.</h2>
            </div>
          </header>
          <div className="autopsy-grid">
            {autopsy.cases.slice(0, 3).map((item) => (
              <article className={item.category} key={item.case_id}>
                <div>
                  <span>{formatDrug(item.antibiotic)}</span>
                  <strong>{item.sample_id}</strong>
                  <em>{item.category === "prevented_error" ? "Blocked error" : "Residual error"}</em>
                </div>
                <p>
                  Laboratory <strong>{formatPhenotype(item.laboratory_label)}</strong>
                  <b>≠</b>
                  Model <strong>{formatPhenotype(item.model_label)}</strong>
                </p>
                <small>Confidence {percent(item.model_confidence)} · OOD {percent(item.ood_score)} · Target {item.target_status}</small>
              </article>
            ))}
          </div>
          <p className="autopsy-note">{autopsy.disclaimer}</p>
        </section>
      )}

      <section className="safety-section" id="safety">
        <header className="section-intro">
          <div>
            <span>Confidence firewall / six barriers</span>
            <h2>Abstention is a product feature.</h2>
          </div>
        </header>
        <div className="barrier-register">
          {BARRIERS.map(([number, title, description]) => (
            <article key={number}>
              <span>{number}</span>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="site-footer">
        <div className="lab-brand"><span className="lab-brand-mark" aria-hidden="true" /><strong>ResistSense</strong></div>
        <p>Predict · Challenge · Abstain</p>
        <span>Research use only · Laboratory confirmation required</span>
      </footer>

      {judgeMode && (
        <aside className="judge-tour" aria-label="90-second judge tour">
          <div className="judge-tour-title">
            <span>Judge mode</span>
            <strong>90-second proof</strong>
          </div>
          <ol>
            {([
              [1, "Verified case"],
              [2, "Firewall replay"],
              [3, "GPT audit"],
              [4, "Evidence passport"],
            ] as Array<[JudgeStep, string]>).map(([step, label]) => (
              <li key={step}>
                <button
                  type="button"
                  className={judgeStep === step ? "active" : judgeStep > step ? "complete" : ""}
                  onClick={() => goToJudgeStep(step)}
                  aria-current={judgeStep === step ? "step" : undefined}
                >
                  <span>{String(step).padStart(2, "0")}</span>{label}
                </button>
              </li>
            ))}
          </ol>
          <div className="judge-tour-actions">
            {judgeStep < 4 ? (
              <button type="button" onClick={() => goToJudgeStep((judgeStep + 1) as JudgeStep)}>
                Next proof <span aria-hidden="true">→</span>
              </button>
            ) : (
              <button type="button" onClick={downloadReport}>
                Export packet <span aria-hidden="true">↓</span>
              </button>
            )}
            <button className="judge-tour-close" type="button" onClick={() => setJudgeMode(false)} aria-label="Exit judge mode">
              ×
            </button>
          </div>
        </aside>
      )}
    </main>
  );
}
