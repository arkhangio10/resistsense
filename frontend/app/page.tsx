"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

type Marker = {
  symbol: string;
  element_type: string;
  resistance_class?: string | null;
  subclass?: string | null;
};

type DrugResult = {
  antibiotic: string;
  final_status: "probable_failure" | "probable_efficacy" | "no_call";
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
  final_status: "probable_failure" | "probable_efficacy" | "no_call";
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

const label: Record<DrugResult["final_status"], string> = {
  probable_failure: "Probable falla",
  probable_efficacy: "Probable eficacia",
  no_call: "No-call",
};

const formatDrug = (name: string) =>
  name
    .split("/")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("/");

const formatPhenotype = (name: "susceptible" | "resistant") =>
  name === "resistant" ? "Resistente" : "Sensible";

const percent = (value: number | null) =>
  value === null ? "—" : `${Math.round(value * 100)}%`;

export default function Home() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [audit, setAudit] = useState<DatasetAudit | null>(null);
  const [autopsy, setAutopsy] = useState<PredictionAutopsy | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [file, setFile] = useState<File | null>(null);
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
    fetch(`${API_URL}/api/v1/prediction-autopsy`, {
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: PredictionAutopsy | null) => setAutopsy(payload))
      .catch(() => setAutopsy(null));
    return () => controller.abort();
  }, []);

  const modelCount = useMemo(
    () => Object.values(readiness?.models || {}).filter(Boolean).length,
    [readiness],
  );

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
            : payload.detail?.message || "No se pudo analizar el FASTA.";
        throw new Error(detail);
      }
      setAnalysis(payload as Analysis);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo conectar con el pipeline.",
      );
    } finally {
      setLoading(false);
    }
  };

  const antibiotics =
    readiness?.antibiotics || [
      "ampicillin",
      "ciprofloxacin",
      "cefotaxime",
      "gentamicin",
      "trimethoprim/sulfamethoxazole",
    ];

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#inicio" aria-label="ResistSense inicio">
          <span className="brand-mark" aria-hidden="true">
            RS
          </span>
          <span>
            <strong>ResistSense</strong>
            <small>Genome Firewall</small>
          </span>
        </a>
        <nav aria-label="Navegación principal">
          <a href="#analisis">Análisis</a>
          <a href="#resultados">Resultados</a>
          <a href="#autopsia">Autopsia</a>
          <a href="#seguridad">Seguridad</a>
        </nav>
        <span className="research-pill">Research prototype</span>
      </header>

      <section className="hero" id="inicio">
        <div className="hero-copy">
          <p className="eyebrow">Predict · Challenge · Abstain</p>
          <h1>
            Detectamos resistencia.
            <span> Bloqueamos confianza insegura.</span>
          </h1>
          <p className="hero-lead">
            Un firewall defensivo que convierte un genoma reconstruido de
            <em> Escherichia coli</em> en evidencia auditable por antibiótico,
            con una salida honesta cuando no existe información suficiente.
          </p>
          <div className="hero-actions">
            <a className="primary-link" href="#analisis">
              Analizar un FASTA
            </a>
            <a className="secondary-link" href="#seguridad">
              Ver barreras de seguridad
            </a>
          </div>
        </div>
        <aside className="system-card" aria-label="Estado del sistema">
          <div className="system-card-head">
            <span>Estado operativo</span>
            <span
              className={`status-dot ${backendOnline ? "online" : "offline"}`}
            >
              {backendOnline === null
                ? "Verificando"
                : backendOnline
                  ? "API conectada"
                  : "API sin conexión"}
            </span>
          </div>
          <div className="readiness-score">
            <strong>{modelCount}</strong>
            <span>/ 5 modelos calibrados</span>
          </div>
          <div className="scope-row">
            <span>Especie</span>
            <strong>E. coli</strong>
          </div>
          <div className="scope-row">
            <span>Política incompleta</span>
            <strong>No-call</strong>
          </div>
          <div className="component-status">
            <span className={readiness?.amrfinderplus ? "ready" : "pending"}>
              AMRFinderPlus
            </span>
            <span
              className={
                readiness?.independent_target_annotator ? "ready" : "pending"
              }
            >
              Diana independiente
            </span>
          </div>
          <p>
            El sistema no inventa resultados: si falta una diana, anotación,
            calibración o modelo, se abstiene.
          </p>
        </aside>
      </section>

      <section className="analysis-shell" id="analisis">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Genome reader</p>
            <h2>Del FASTA a una decisión trazable</h2>
          </div>
          <span className="step-indicator">01 / Carga y validación</span>
        </div>

        <div className="upload-grid">
          <label className={`dropzone ${file ? "has-file" : ""}`}>
            <input
              type="file"
              accept=".fa,.fna,.fasta,text/plain"
              onChange={handleFile}
            />
            <span className="upload-icon" aria-hidden="true">
              ↑
            </span>
            <strong>{file ? file.name : "Selecciona un genoma reconstruido"}</strong>
            <span>
              {file
                ? `${(file.size / 1_000_000).toFixed(2)} MB · listo para validar`
                : "Archivo FASTA en formato .fa, .fna o .fasta · máximo 15 MB"}
            </span>
          </label>

          <div className="preflight-card">
            <h3>Controles antes de predecir</h3>
            <ul>
              <li>Formato, longitud, contigs y bases ambiguas</li>
              <li>Genes y mutaciones mediante AMRFinderPlus</li>
              <li>Similitud con grupos usados en entrenamiento</li>
              <li>Calibración, conformal y verificación de diana</li>
            </ul>
            <button type="button" onClick={analyze} disabled={!file || loading}>
              {loading ? "Atravesando el firewall…" : "Ejecutar análisis seguro"}
            </button>
            {error && <p className="error-message">{error}</p>}
          </div>
        </div>
      </section>

      {analysis && (
        <section className="results-section" id="resultados">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Decision report</p>
              <h2>Tribunal de evidencia</h2>
            </div>
            <span className={`qc-badge ${analysis.qc.passed ? "pass" : "fail"}`}>
              QC {analysis.qc.passed ? "aprobado" : "no aprobado"}
            </span>
          </div>

          <div className="qc-strip">
            <div>
              <span>Longitud</span>
              <strong>{(analysis.qc.total_length_bp / 1_000_000).toFixed(2)} Mb</strong>
            </div>
            <div>
              <span>Contigs</span>
              <strong>{analysis.qc.contigs}</strong>
            </div>
            <div>
              <span>Bases ambiguas</span>
              <strong>{percent(analysis.qc.ambiguous_fraction)}</strong>
            </div>
            <div>
              <span>AMRFinderPlus</span>
              <strong>{analysis.annotation.available ? "Disponible" : "No disponible"}</strong>
            </div>
          </div>

          <div className="result-grid">
            {analysis.results.map((result) => (
              <article className={`drug-card ${result.final_status}`} key={result.antibiotic}>
                <div className="drug-card-head">
                  <div>
                    <span>Antibiótico</span>
                    <h3>{formatDrug(result.antibiotic)}</h3>
                  </div>
                  <span className="result-badge">{label[result.final_status]}</span>
                </div>
                <div className="confidence-row">
                  <div>
                    <span>Confianza calibrada</span>
                    <strong>{percent(result.confidence)}</strong>
                  </div>
                  <div>
                    <span>Evidencia</span>
                    <strong>{result.evidence_level.slice(0, 1)}</strong>
                  </div>
                  <div>
                    <span>Diana</span>
                    <strong>{result.target_status}</strong>
                  </div>
                </div>
                <p>{result.explanation}</p>
                {result.no_call_reasons.length > 0 && (
                  <div className="reason-list">
                    {result.no_call_reasons.map((reason) => (
                      <span key={reason}>{reason.replaceAll("_", " ")}</span>
                    ))}
                  </div>
                )}
                {Object.entries(result.model_probabilities).map(([model, value]) => (
                  <div className="model-vote" key={model}>
                    <span>{model.replaceAll("_", " ")}</span>
                    <div>
                      <i style={{ width: `${value * 100}%` }} />
                    </div>
                    <strong>{percent(value)}</strong>
                  </div>
                ))}
              </article>
            ))}
          </div>

          <div className="disclaimer">{analysis.disclaimer}</div>
        </section>
      )}

      {!analysis && (
        <section className="coverage-section" id="resultados">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Scope control</p>
              <h2>Cinco decisiones, una política de seguridad</h2>
            </div>
            <span className="step-indicator">E. coli · taxon 562</span>
          </div>
          <div className="coverage-list">
            {antibiotics.map((antibiotic, index) => (
              <div key={antibiotic}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{formatDrug(antibiotic)}</strong>
                <em>{readiness?.models[antibiotic] ? "Modelo listo" : "Pendiente"}</em>
              </div>
            ))}
          </div>
        </section>
      )}

      {audit && (
        <section className="evidence-section" id="vigilancia">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Verified cohort</p>
              <h2>Cohorte autocurada con particiones congeladas</h2>
            </div>
            <span className="step-indicator">BV-BRC · Laboratory Method</span>
          </div>
          <p className="audit-warning">
            Los organizadores permiten construir un dataset propio. ResistSense
            conserva solamente mediciones de laboratorio, excluye conflictos y
            mantiene grupos genéticos completos dentro de cada partición.
          </p>
          <div className="audit-kpis">
            <div><strong>{audit.unique_genomes.toLocaleString("es-PE")}</strong><span>genomas únicos</span></div>
            <div><strong>{audit.genetic_clusters.toLocaleString("es-PE")}</strong><span>clústeres cgMLST</span></div>
            <div><strong>{audit.preliminary_qc_pass_pct.toFixed(2)}%</strong><span>pasa QC de metadatos</span></div>
          </div>
          <div className="audit-table" role="table" aria-label="Balance fenotípico">
            <div className="audit-table-head" role="row">
              <span>Antibiótico</span><span>Pares</span><span>Resistentes</span><span>R %</span>
            </div>
            {audit.antibiotics.map((item) => (
              <div role="row" key={item.antibiotic}>
                <strong>{formatDrug(item.antibiotic)}</strong>
                <span>{item.eligible_pairs.toLocaleString("es-PE")}</span>
                <span>{item.resistant_pairs.toLocaleString("es-PE")}</span>
                <div className="prevalence">
                  <i style={{ width: `${item.resistant_pct}%` }} />
                  <em>{item.resistant_pct.toFixed(1)}%</em>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {autopsy && (
        <section className="autopsy-section" id="autopsia">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Prediction Autopsy</p>
              <h2>Los errores no se esconden: se investigan</h2>
            </div>
            <span className="step-indicator">Test congelado · casos reales</span>
          </div>

          <p className="autopsy-intro">
            Cada expediente proviene de un genoma del test que nunca participó
            en entrenamiento ni calibración. Mostramos tanto errores detenidos
            por el firewall como errores residuales que lograron atravesarlo.
          </p>

          <div className="autopsy-kpis">
            <div>
              <strong>{autopsyTotals.errors}</strong>
              <span>errores del modelo base</span>
            </div>
            <div>
              <strong>{autopsyTotals.prevented}</strong>
              <span>bloqueados por el firewall</span>
            </div>
            <div>
              <strong>{autopsyTotals.escaped}</strong>
              <span>errores residuales emitidos</span>
            </div>
          </div>

          <div className="autopsy-grid">
            {autopsy.cases.map((item) => (
              <article
                className={`autopsy-card ${item.category}`}
                key={item.case_id}
              >
                <div className="autopsy-card-head">
                  <div>
                    <span>{formatDrug(item.antibiotic)}</span>
                    <h3>{item.sample_id}</h3>
                    <small>Grupo genético {item.genetic_group}</small>
                  </div>
                  <em>
                    {item.category === "prevented_error"
                      ? "Error bloqueado"
                      : "Error residual"}
                  </em>
                </div>

                <div className="autopsy-comparison">
                  <div>
                    <span>Laboratorio</span>
                    <strong>{formatPhenotype(item.laboratory_label)}</strong>
                  </div>
                  <b aria-hidden="true">≠</b>
                  <div>
                    <span>Modelo</span>
                    <strong>{formatPhenotype(item.model_label)}</strong>
                  </div>
                  <div>
                    <span>Confianza</span>
                    <strong>{percent(item.model_confidence)}</strong>
                  </div>
                </div>

                <div className="autopsy-signals">
                  <span>OOD {percent(item.ood_score)}</span>
                  <span>Diana {item.target_status}</span>
                  <span>Salida {item.final_status.replaceAll("_", " ")}</span>
                </div>

                {item.no_call_reasons.length > 0 && (
                  <div className="reason-list">
                    {item.no_call_reasons.map((reason) => (
                      <span key={reason}>{reason.replaceAll("_", " ")}</span>
                    ))}
                  </div>
                )}

                {item.known_markers.length > 0 && (
                  <p className="autopsy-markers">
                    Evidencia observada: {item.known_markers.join(", ")}
                  </p>
                )}

                <p className="autopsy-lesson">
                  {item.category === "prevented_error"
                    ? "La abstención evitó publicar una conclusión incorrecta."
                    : "Este fallo atravesó todas las barreras y permanece visible para auditoría."}
                </p>
              </article>
            ))}
          </div>

          <div className="disclaimer">{autopsy.disclaimer}</div>
        </section>
      )}

      <section className="firewall-section" id="seguridad">
        <div className="section-heading light">
          <div>
            <p className="eyebrow">Confidence firewall</p>
            <h2>Seis barreras antes de publicar una conclusión</h2>
          </div>
          <span className="step-indicator">Safety by construction</span>
        </div>
        <div className="barrier-grid">
          {[
            ["01", "Calidad genómica", "Rechaza ensamblajes incompletos, atípicos o ambiguos."],
            ["02", "Diana molecular", "Nunca asume eficacia por ausencia de marcadores."],
            ["03", "Fuera de distribución", "Mide cercanía a los grupos del entrenamiento."],
            ["04", "Desacuerdo", "Compara las probabilidades de cada experto."],
            ["05", "Calibración", "La confianza debe corresponder con rendimiento real."],
            ["06", "Conformal", "Un conjunto ambiguo activa automáticamente no-call."],
          ].map(([number, title, description]) => (
            <article key={number}>
              <span>{number}</span>
              <h3>{title}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer>
        <div className="brand footer-brand">
          <span className="brand-mark" aria-hidden="true">RS</span>
          <span><strong>ResistSense</strong><small>Genome Firewall</small></span>
        </div>
        <p>
          Prototipo de investigación defensiva. No identifica especies, no
          recomienda tratamientos y no sustituye pruebas de laboratorio.
        </p>
        <span>Predict · Challenge · Abstain</span>
      </footer>
    </main>
  );
}
