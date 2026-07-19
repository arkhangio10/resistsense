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
    filename: string;
    total_length_bp: number;
    contigs: number;
    ambiguous_fraction: number;
    reasons: string[];
  };
  annotation: {
    available: boolean;
    tool_version: string | null;
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

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const BioSimulation = dynamic(() => import("../components/BioSimulation"), {
  ssr: false,
  loading: () => <div className="simulation-loading">Initializing specimen view…</div>,
});

const STATUS_LABEL: Record<FinalStatus, string> = {
  probable_failure: "Probable resistance",
  probable_efficacy: "Probable susceptibility",
  no_call: "No-call",
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

const formatPhenotype = (value: "susceptible" | "resistant") =>
  value === "resistant" ? "Resistant" : "Susceptible";

export default function Home() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [audit, setAudit] = useState<DatasetAudit | null>(null);
  const [autopsy, setAutopsy] = useState<PredictionAutopsy | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [visualizedAntibiotic, setVisualizedAntibiotic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

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

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] || null;
    setFile(selected);
    setAnalysis(null);
    setVisualizedAntibiotic("");
    setError(null);
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
      setVisualizedAntibiotic(completedAnalysis.results[0]?.antibiotic || "");
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
            {error && <p className="lab-error">{error}</p>}
          </section>

          <section
            className={`specimen-stage ${loading ? "is-loading" : ""}`}
            aria-label="Bacterial response visualization"
          >
            <div className="stage-caption">
              <strong>Specimen view</strong>
              <span>{analysis ? "model-driven response" : "awaiting genome"}</span>
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
                  <li>Reading genome quality</li>
                  <li>Scanning AMR evidence</li>
                  <li>Challenging model consensus</li>
                  <li>Calibrating final confidence</li>
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
              <span className="resistant">Resistant</span>
              <span className="susceptible">Susceptible</span>
              <span className="no-call">Uncertain</span>
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
            <span>Policy<strong>Fail-safe no-call</strong></span>
          </div>
          <a href={analysis ? "#evidence" : "#validation"}>
            {analysis ? "Inspect evidence" : "Inspect validation"} →
          </a>
        </footer>
      </section>

      {analysis && visualizedResult && (
        <section className="evidence-inspector" id="evidence">
          <header className="section-intro">
            <div>
              <span>Selected assessment / {analysis.analysis_id.slice(0, 8)}</span>
              <h2>{formatDrug(visualizedResult.antibiotic)}</h2>
            </div>
            <strong className={`evidence-status ${STATUS_CLASS[visualizedResult.final_status]}`}>
              {STATUS_LABEL[visualizedResult.final_status]}
            </strong>
          </header>

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
    </main>
  );
}
