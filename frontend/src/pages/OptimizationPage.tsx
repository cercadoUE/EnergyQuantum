import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Download,
  FlaskConical,
  Gauge,
  Info,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
  TriangleAlert,
  Zap,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import MapCanvas from "../components/MapCanvas";
import { Badge, ErrorState, Field, Panel, SectionTitle, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import type { NetworkSummary, OptimizeResponse, RunResult, SubnetPreview } from "../lib/types";
import { downloadCsv, downloadJson, km, pct, seconds } from "../lib/format";

const ALGORITHMS = ["Exacto", "Búsqueda local", "Kernighan–Lin", "QAOA"];
const WEIGHT_MODES = [
  { value: "length", label: "A · longitud (km)" },
  { value: "normalized", label: "B · longitud / mediana" },
  { value: "synthetic", label: "D · escenario sintético" },
];
const DEMAND_MODES = [
  { value: "uniform", label: "Uniforme abstracta (SIMULADO)" },
  { value: "capacity_proxy", label: "Proxy por capacidad (DERIVADO)" },
];

const CHART_COLORS = ["#22d3ee", "#3b82f6", "#34d399", "#fbbf24", "#fb7185"];

function isFeasible(run: RunResult | undefined): boolean {
  if (!run) return false;
  if (run.feasible !== undefined) return Boolean(run.feasible);
  const validation = run.validation as Record<string, unknown> | undefined;
  return Boolean(validation?.feasible);
}

export default function OptimizationPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [summary, setSummary] = useState<NetworkSummary | null>(null);
  const [componentIndex, setComponentIndex] = useState(Number(params.get("component") ?? 0));
  const [size, setSize] = useState(Number(params.get("size") ?? 6));
  const [seedNode, setSeedNode] = useState(params.get("seed") ?? "");
  const [preview, setPreview] = useState<SubnetPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [weightMode, setWeightMode] = useState("length");
  const [demandMode, setDemandMode] = useState("uniform");
  const [demandValue, setDemandValue] = useState(1);
  const [seed, setSeed] = useState(7);
  const [alpha, setAlpha] = useState(1);
  const [beta, setBeta] = useState(3);
  const [restarts, setRestarts] = useState(12);
  const [selectedAlgorithms, setSelectedAlgorithms] = useState<string[]>(ALGORITHMS);
  const [qaoaP, setQaoaP] = useState(1);
  const [qaoaShots, setQaoaShots] = useState(2048);
  const [qaoaMaxiter, setQaoaMaxiter] = useState(60);
  const [qaoaTimeLimit, setQaoaTimeLimit] = useState(60);
  const [qaoaMaxEvaluations, setQaoaMaxEvaluations] = useState(400);
  const [failedEdges, setFailedEdges] = useState<string[]>([]);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [selectedRun, setSelectedRun] = useState<string>("Exacto");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.summary().then(setSummary).catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    setPreviewError(null);
    api
      .subnet({ component_index: componentIndex, max_nodes: size, seed_node: seedNode || null })
      .then((payload) => {
        if (!cancelled) {
          setPreview(payload);
          setFailedEdges([]);
          setResult(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setPreviewError(String(err?.message ?? err));
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [componentIndex, size, seedNode]);

  const subnet = preview?.subnet ?? null;
  const partition = result?.runs[selectedRun]?.partition?.assignment ?? null;
  const bestRun = useMemo(() => {
    if (!result) return null;
    return Object.values(result.runs)
      .filter((run) => run.objective !== null && run.objective !== undefined)
      .sort((a, b) => Number(a.objective) - Number(b.objective))[0];
  }, [result]);

  const comparisonData = useMemo(() => {
    if (!result) return [];
    return Object.entries(result.runs).map(([name, run]) => ({
      name: name.replace("Kernighan–Lin", "K–L"),
      H: run.objective === null || run.objective === undefined ? null : Number(run.objective.toFixed(5)),
      cut: run.cut === null || run.cut === undefined ? null : Number(run.cut.toFixed(3)),
      seconds: Number(run.seconds.toFixed(3)),
    }));
  }, [result]);

  const qaoaRun = result?.runs["QAOA"];
  const qaoaTrace = useMemo(() => {
    if (!qaoaRun?.trace) return [];
    return qaoaRun.trace.map((value, index) => ({ iter: index + 1, H: Number(value.toFixed(6)) }));
  }, [qaoaRun]);

  const qaoaCounts = useMemo(() => {
    if (!qaoaRun?.counts) return [];
    const entries = Object.entries(qaoaRun.counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([bits, count]) => ({ bits, count }));
    const total = Object.values(qaoaRun.counts).reduce((sum, value) => sum + value, 0);
    return entries.map((row) => ({ ...row, pct: total ? row.count / total : 0 }));
  }, [qaoaRun]);

  function toggleAlgorithm(name: string) {
    setSelectedAlgorithms((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    );
  }

  async function runOptimization() {
    if (!subnet) return;
    setRunning(true);
    setError(null);
    try {
      const payload = {
        component_index: componentIndex,
        max_nodes: size,
        seed_node: seedNode || null,
        weight_mode: weightMode,
        demand_mode: demandMode,
        demand_value: demandValue,
        seed,
        alpha,
        beta,
        algorithms: selectedAlgorithms,
        restarts,
        qaoa_p: qaoaP,
        qaoa_shots: qaoaShots,
        qaoa_maxiter: qaoaMaxiter,
        qaoa_time_limit: qaoaTimeLimit,
        qaoa_max_evaluations: qaoaMaxEvaluations,
        failed_edge_ids: failedEdges,
      };
      const response = await api.optimize(payload);
      setResult(response);
      const first = Object.keys(response.runs)[0];
      setSelectedRun(first ?? "Exacto");
    } catch (err) {
      setError(String((err as Error)?.message ?? err));
    } finally {
      setRunning(false);
    }
  }

  function exportJson() {
    if (!result) return;
    downloadJson(`energyquantum-optimizacion-${componentIndex}-${size}.json`, result);
  }

  function exportCsv() {
    if (!result) return;
    const rows = Object.entries(result.runs).map(([name, run]) => ({
      metodo: name,
      H: run.objective,
      corte: run.cut,
      balance: run.balance,
      segundos: run.seconds,
      factible: isFeasible(run),
      estado: run.status ?? "completed",
      particion: run.bits ? run.bits.join("") : "",
    }));
    downloadCsv(`energyquantum-optimizacion-${componentIndex}-${size}.csv`, rows);
  }

  if (!summary) {
    return (
      <div className="page-pad loading-page">
        <Spinner label="Preparando laboratorio…" />
      </div>
    );
  }

  return (
    <div className="split-page split-page--wide-aside">
      <div className="split-page__map">
        <MapCanvas
          mode="subnet"
          subnet={subnet}
          partition={partition}
          failedEdgeIds={failedEdges}
          layers={{
            verifiedLines: true,
            unverifiedLines: false,
            stations: true,
            generation: false,
            labels: true,
          }}
        />
        <div className="map-float map-float--top map-float--legend">
          <span className="legend-dot" style={{ background: "#0ea5e9" }} /> Grupo A
          <span className="legend-dot" style={{ background: "#f97316" }} /> Grupo B
          <span className="legend-dot" style={{ background: "#f43f5e" }} /> Falla
        </div>
        {running && (
          <div className="map-float map-float--center">
            <div className="run-overlay">
              <Loader2 size={26} className="spin" />
              <strong>Ejecutando {selectedAlgorithms.join(" · ")}</strong>
              <span>QAOA puede tardar hasta {qaoaTimeLimit}s según el presupuesto.</span>
            </div>
          </div>
        )}
        {!subnet && previewLoading && (
          <div className="map-float map-float--center">
            <Spinner label="Construyendo subred…" />
          </div>
        )}
        {previewError && (
          <div className="map-float map-float--center">
            <ErrorState title="Subred no disponible" message={previewError} />
          </div>
        )}
      </div>

      <aside className="split-page__aside">
        <Panel>
          <SectionTitle
            eyebrow="Instancia real"
            title="Configuración del experimento"
            description="Los IDs originales se conservan; el solver recibe índices densos 0..n−1."
          />

          <div className="grid-2">
            <Field label="Componente">
              <select
                className="select"
                value={componentIndex}
                onChange={(event) => setComponentIndex(Number(event.target.value))}
              >
                {summary.components.map((row) => (
                  <option key={row.index} value={row.index}>
                    {row.label} · {row.nodes} nodos
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Nodos · ${size}`}>
              <input
                className="range"
                type="range"
                min={2}
                max={12}
                value={size}
                onChange={(event) => setSize(Number(event.target.value))}
              />
            </Field>
          </div>

          <div className="grid-2">
            <Field label="α · costo">
              <input
                className="input"
                type="number"
                min={0}
                step={0.1}
                value={alpha}
                onChange={(event) => setAlpha(Number(event.target.value))}
              />
            </Field>
            <Field label="β · balance">
              <input
                className="input"
                type="number"
                min={0.1}
                step={0.1}
                value={beta}
                onChange={(event) => setBeta(Number(event.target.value))}
              />
            </Field>
          </div>

          <div className="grid-2">
            <Field label="Pesos">
              <select className="select" value={weightMode} onChange={(event) => setWeightMode(event.target.value)}>
                {WEIGHT_MODES.map((mode) => (
                  <option key={mode.value} value={mode.value}>
                    {mode.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Demanda">
              <select className="select" value={demandMode} onChange={(event) => setDemandMode(event.target.value)}>
                {DEMAND_MODES.map((mode) => (
                  <option key={mode.value} value={mode.value}>
                    {mode.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="grid-2">
            <Field label="Demanda por nodo" hint="Solo si el modo es uniforme.">
              <input
                className="input"
                type="number"
                min={0.1}
                step={0.1}
                value={demandValue}
                onChange={(event) => setDemandValue(Number(event.target.value))}
              />
            </Field>
            <Field label="Semilla">
              <input
                className="input"
                type="number"
                value={seed}
                onChange={(event) => setSeed(Number(event.target.value))}
              />
            </Field>
          </div>

          <div className="field">
            <span className="field__label">Algoritmos</span>
            <div className="algorithm-grid">
              {ALGORITHMS.map((name) => (
                <button
                  key={name}
                  type="button"
                  className={`algorithm-toggle ${selectedAlgorithms.includes(name) ? "is-on" : ""}`}
                  onClick={() => toggleAlgorithm(name)}
                >
                  {selectedAlgorithms.includes(name) ? <CheckCircle2 size={15} /> : <span className="algorithm-toggle__empty" />}
                  {name}
                </button>
              ))}
            </div>
          </div>

          <details className="config-details">
            <summary>
              <FlaskConical size={15} /> Parámetros QAOA
            </summary>
            <div className="grid-2">
              <Field label="Capas p">
                <input className="input" type="number" min={1} max={4} value={qaoaP} onChange={(e) => setQaoaP(Number(e.target.value))} />
              </Field>
              <Field label="Shots">
                <input className="input" type="number" min={1} max={100000} value={qaoaShots} onChange={(e) => setQaoaShots(Number(e.target.value))} />
              </Field>
              <Field label="Maxiter">
                <input className="input" type="number" min={1} max={300} value={qaoaMaxiter} onChange={(e) => setQaoaMaxiter(Number(e.target.value))} />
              </Field>
              <Field label="Límite (s)">
                <input className="input" type="number" min={1} max={600} value={qaoaTimeLimit} onChange={(e) => setQaoaTimeLimit(Number(e.target.value))} />
              </Field>
              <Field label="Máx. evaluaciones">
                <input className="input" type="number" min={1} max={5000} value={qaoaMaxEvaluations} onChange={(e) => setQaoaMaxEvaluations(Number(e.target.value))} />
              </Field>
              <Field label="Reinicios heurísticos">
                <input className="input" type="number" min={1} max={100} value={restarts} onChange={(e) => setRestarts(Number(e.target.value))} />
              </Field>
            </div>
          </details>

          {!!preview?.bridge_edges.length && (
            <div className="field">
              <span className="field__label">Fallas a excluir del corte</span>
              <div className="failure-options">
                {preview.bridge_edges.slice(0, 5).map((edge) => (
                  <label key={edge.id} className="check-row">
                    <input
                      type="checkbox"
                      checked={failedEdges.includes(edge.id)}
                      onChange={(event) =>
                        setFailedEdges((current) =>
                          event.target.checked
                            ? [...current, edge.id]
                            : current.filter((id) => id !== edge.id),
                        )
                      }
                    />
                    <span>
                      {edge.source_name} ↔ {edge.target_name}
                      <small>{km(edge.length_km)} · puente</small>
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="button-row">
            <button className="button button--primary" onClick={runOptimization} disabled={!subnet || running || !selectedAlgorithms.length}>
              {running ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
              {running ? "Ejecutando…" : "Ejecutar experimento"}
            </button>
            <button
              className="button button--ghost"
              onClick={() => {
                setResult(null);
                setFailedEdges([]);
                setError(null);
              }}
            >
              <RotateCcw size={14} /> Limpiar
            </button>
          </div>

          {error && <ErrorState title="Error de ejecución" message={error} />}

          <div className="warning-strip">
            <TriangleAlert size={15} />
            <span>
              Demanda y pesos sintéticos son supuestos de escenario. La generación se fija en 0;
              el resultado no representa operación eléctrica.
            </span>
          </div>
        </Panel>

        {result && (
          <>
            <Panel>
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">Resultados</div>
                  <h3>Comparación de métodos</h3>
                </div>
                <div className="button-row button-row--tight">
                  <button className="icon-button" onClick={exportJson} title="Exportar JSON">
                    <Download size={15} />
                  </button>
                  <button className="icon-button" onClick={exportCsv} title="Exportar CSV">
                    <BarChart3 size={15} />
                  </button>
                </div>
              </div>

              <div className="mini-stats">
                <StatCard
                  label="Mejor H"
                  value={bestRun ? Number(bestRun.objective).toFixed(5) : "—"}
                  tone="cyan"
                  icon={<Sparkles size={15} />}
                />
                <StatCard
                  label="Corte"
                  value={bestRun ? Number(bestRun.cut).toFixed(2) : "—"}
                  tone="blue"
                  icon={<Gauge size={15} />}
                />
                <StatCard
                  label="Tiempo total"
                  value={`${result.elapsed_seconds.toFixed(2)}s`}
                  tone="green"
                  icon={<Zap size={15} />}
                />
                <StatCard
                  label="QAOA"
                  value={qaoaRun?.status === "completed" ? "OK" : qaoaRun?.status ?? "—"}
                  tone={qaoaRun?.status === "completed" ? "green" : "amber"}
                  icon={<FlaskConical size={15} />}
                />
              </div>

              <div className="run-cards">
                {Object.entries(result.runs).map(([name, run], index) => (
                  <button
                    key={name}
                    className={`run-card ${selectedRun === name ? "is-active" : ""}`}
                    onClick={() => setSelectedRun(name)}
                  >
                    <span className="run-card__top">
                      <span className="run-card__dot" style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} />
                      <strong>{name}</strong>
                      <Badge tone={isFeasible(run) ? "green" : "amber"}>
                        {isFeasible(run) ? "Factible" : "No factible"}
                      </Badge>
                    </span>
                    <span className="run-card__metrics">
                      <span>
                        <small>H</small>
                        <strong className="mono">{run.objective === null ? "—" : Number(run.objective).toFixed(5)}</strong>
                      </span>
                      <span>
                        <small>Corte</small>
                        <strong className="mono">{run.cut === null ? "—" : Number(run.cut).toFixed(2)}</strong>
                      </span>
                      <span>
                        <small>Tiempo</small>
                        <strong className="mono">{seconds(run.seconds)}</strong>
                      </span>
                    </span>
                    {run.status && run.status !== "completed" && (
                      <span className="run-card__status">{run.status}</span>
                    )}
                  </button>
                ))}
              </div>

              <div className="chart-block">
                <div className="chart-block__head">
                  <span>H por método</span>
                  <small>Menor es mejor</small>
                </div>
                <div className="chart-block__body">
                  <ResponsiveContainer width="100%" height={190}>
                    <BarChart data={comparisonData} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                      <CartesianGrid stroke="rgba(148,163,184,.12)" vertical={false} />
                      <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{
                          background: "#0f172a",
                          border: "1px solid rgba(148,163,184,.2)",
                          borderRadius: 10,
                          color: "#e2e8f0",
                          fontSize: 12,
                        }}
                      />
                      <Bar dataKey="H" radius={[5, 5, 0, 0]}>
                        {comparisonData.map((_, index) => (
                          <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </Panel>

            <Panel>
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">Partición seleccionada</div>
                  <h3>{selectedRun}</h3>
                </div>
                <Badge tone="cyan">{result.runs[selectedRun]?.partition?.groups.A.length ?? 0} / {result.runs[selectedRun]?.partition?.groups.B.length ?? 0}</Badge>
              </div>
              <div className="partition-grid">
                {["A", "B"].map((group) => {
                  const ids = result.runs[selectedRun]?.partition?.groups[group as "A" | "B"] ?? [];
                  return (
                    <div className={`partition-col partition-col--${group.toLowerCase()}`} key={group}>
                      <div className="partition-col__head">Grupo {group}</div>
                      {ids.map((id) => {
                        const node = result.subnet.nodes.find((row) => row.id === id);
                        return (
                          <div className="partition-node" key={id}>
                            <span>{node?.name ?? id}</span>
                            <small className="mono">{node?.voltage_kv ?? "—"} kV</small>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
              <div className="info-strip info-strip--muted">
                <Info size={14} />
                <span>
                  H = α · corte / Σpesos + β · desbalance². El corte se mide sobre aristas
                  disponibles; las fallas seleccionadas se excluyen.
                </span>
              </div>
            </Panel>

            {qaoaRun && qaoaRun.trace && qaoaRun.trace.length > 0 && (
              <Panel>
                <div className="panel-heading">
                  <div>
                    <div className="eyebrow">QAOA · Aer</div>
                    <h3>Convergencia y muestreo</h3>
                  </div>
                  <Badge tone={qaoaRun.status === "completed" ? "green" : "amber"}>
                    {qaoaRun.status ?? "—"}
                  </Badge>
                </div>
                <div className="qaoa-meta">
                  <span><small>Qubits</small><strong className="mono">{qaoaRun.qubits ?? "—"}</strong></span>
                  <span><small>p</small><strong className="mono">{qaoaRun.p ?? "—"}</strong></span>
                  <span><small>Shots</small><strong className="mono">{qaoaRun.shots ?? "—"}</strong></span>
                  <span><small>Factible</small><strong className="mono">{pct(qaoaRun.feasible_fraction)}</strong></span>
                  <span><small>Evaluaciones</small><strong className="mono">{qaoaRun.evaluations ?? "—"}</strong></span>
                </div>
                <div className="chart-block__body">
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={qaoaTrace} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                      <CartesianGrid stroke="rgba(148,163,184,.12)" vertical={false} />
                      <XAxis dataKey="iter" tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{
                          background: "#0f172a",
                          border: "1px solid rgba(148,163,184,.2)",
                          borderRadius: 10,
                          color: "#e2e8f0",
                          fontSize: 12,
                        }}
                      />
                      <Line type="monotone" dataKey="H" stroke="#22d3ee" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                {!!qaoaCounts.length && (
                  <div className="chart-block">
                    <div className="chart-block__head">
                      <span>Muestras más frecuentes</span>
                      <small>Top 12</small>
                    </div>
                    <div className="chart-block__body">
                      <ResponsiveContainer width="100%" height={190}>
                        <BarChart data={qaoaCounts} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                          <CartesianGrid stroke="rgba(148,163,184,.12)" vertical={false} />
                          <XAxis dataKey="bits" tick={{ fill: "#94a3b8", fontSize: 9 }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} />
                          <Tooltip
                            contentStyle={{
                              background: "#0f172a",
                              border: "1px solid rgba(148,163,184,.2)",
                              borderRadius: 10,
                              color: "#e2e8f0",
                              fontSize: 12,
                            }}
                          />
                          <Bar dataKey="count" fill="#34d399" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </Panel>
            )}

            <Panel>
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">Siguiente paso</div>
                  <h3>Comparar o simular una falla</h3>
                </div>
              </div>
              <div className="button-row">
                <button className="button button--primary button--sm" onClick={() => navigate("/comparacion")}>
                  <BarChart3 size={14} /> Ver comparación <ArrowRight size={14} />
                </button>
                <button className="button button--ghost button--sm" onClick={() => navigate(`/fallas?component=${componentIndex}&size=${size}${seedNode ? `&seed=${seedNode}` : ""}`)}>
                  <Zap size={14} /> Simular falla
                </button>
              </div>
            </Panel>
          </>
        )}
      </aside>
    </div>
  );
}
