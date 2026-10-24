import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  FlaskConical,
  Info,
  Loader2,
  Play,
  Sparkles,
  TriangleAlert,
  Zap,
} from "lucide-react";
import { Badge, ErrorState, Field, Panel, SectionTitle, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import type { RunResult, SyntheticNetwork, SyntheticOptimizeResponse } from "../lib/types";
import { seconds } from "../lib/format";

const ALGORITHMS = ["Exacto", "Búsqueda local", "Kernighan–Lin", "QAOA"];
const COLORS = ["#22d3ee", "#3b82f6", "#34d399", "#fbbf24"];

function isFeasible(run: RunResult | undefined): boolean {
  if (!run) return false;
  if (run.feasible !== undefined) return Boolean(run.feasible);
  return Boolean((run.validation as Record<string, unknown> | undefined)?.feasible);
}

export default function SyntheticPage() {
  const navigate = useNavigate();
  const [network, setNetwork] = useState<SyntheticNetwork | null>(null);
  const [nodes, setNodes] = useState(12);
  const [alpha, setAlpha] = useState(1);
  const [beta, setBeta] = useState(3);
  const [seed, setSeed] = useState(7);
  const [algorithms, setAlgorithms] = useState<string[]>(ALGORITHMS);
  const [qaoaP, setQaoaP] = useState(1);
  const [qaoaShots, setQaoaShots] = useState(2048);
  const [qaoaMaxiter, setQaoaMaxiter] = useState(60);
  const [result, setResult] = useState<SyntheticOptimizeResponse | null>(null);
  const [selectedRun, setSelectedRun] = useState("Exacto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .syntheticNetwork(nodes)
      .then((payload) => {
        if (!cancelled) {
          setNetwork(payload.network);
          setResult(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String((err as Error)?.message ?? err));
      });
    return () => {
      cancelled = true;
    };
  }, [nodes]);

  const partition = result?.runs[selectedRun]?.partition?.assignment ?? null;
  const best = useMemo(() => {
    if (!result) return null;
    return Object.entries(result.runs)
      .filter(([, run]) => run.objective !== null && run.objective !== undefined)
      .sort((a, b) => Number(a[1].objective) - Number(b[1].objective))[0];
  }, [result]);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const response = await api.syntheticOptimize({
        nodes,
        seed,
        alpha,
        beta,
        algorithms,
        qaoa_p: qaoaP,
        qaoa_shots: qaoaShots,
        qaoa_maxiter: qaoaMaxiter,
        qaoa_time_limit: 60,
        qaoa_max_evaluations: 400,
      });
      setResult(response);
      setSelectedRun(Object.keys(response.runs)[0] ?? "Exacto");
    } catch (err) {
      setError(String((err as Error)?.message ?? err));
    } finally {
      setLoading(false);
    }
  }

  if (!network) {
    return (
      <div className="page-pad loading-page">
        {error ? (
          <ErrorState title="API no disponible" message={error} />
        ) : (
          <Spinner label="Cargando red sintética…" />
        )}
      </div>
    );
  }

  return (
    <div className="page-pad synthetic-page">
      <section className="synthetic-hero">
        <div>
          <div className="eyebrow">Laboratorio separado</div>
          <h2>Red sintética de {network.nodes.length} nodos</h2>
          <p>
            Localidades reales, pero enlaces, demanda, generación y capacidades son supuestos
            inventados. No se mezcla con la capa OSINERGMIN.
          </p>
        </div>
        <div className="quality-note">
          <Badge tone="amber">SIMULADO</Badge>
          <Badge tone="slate">Sin datos reales</Badge>
          <Badge tone="cyan">Hasta 12 nodos</Badge>
        </div>
      </section>

      <div className="synthetic-grid">
        <Panel className="synthetic-map-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Instancia</div>
              <h3>Grafo y partición</h3>
            </div>
            <Badge tone="amber">{nodes} nodos</Badge>
          </div>
          <div className="synthetic-graph">
            <svg viewBox="-8 -8 116 116" role="img" aria-label="Grafo sintético">
              {network.edges.map((edge, index) => {
                const a = network.nodes[edge.source];
                const b = network.nodes[edge.target];
                if (!a || !b) return null;
                const [x1, y1] = a.position;
                const [x2, y2] = b.position;
                const cut =
                  partition &&
                  partition[String(edge.source)] !== undefined &&
                  partition[String(edge.source)] !== partition[String(edge.target)];
                return (
                  <line
                    key={index}
                    x1={x1 * 100}
                    y1={100 - y1 * 100}
                    x2={x2 * 100}
                    y2={100 - y2 * 100}
                    stroke={cut ? "#f97316" : "#94a3b8"}
                    strokeWidth={cut ? 1.8 : 1}
                    strokeOpacity={cut ? 0.9 : 0.45}
                    strokeDasharray={edge.available ? undefined : "2 2"}
                  />
                );
              })}
              {network.nodes.map((node) => {
                const [x, y] = node.position;
                const group = partition?.[String(node.id)];
                const fill = group === 0 ? "#0ea5e9" : group === 1 ? "#f97316" : "#0f766e";
                return (
                  <g key={node.id}>
                    <circle
                      cx={x * 100}
                      cy={100 - y * 100}
                      r={3.8}
                      fill={fill}
                      stroke="#ffffff"
                      strokeWidth={1.2}
                    />
                    <text
                      x={x * 100}
                      y={100 - y * 100 + 7.5}
                      textAnchor="middle"
                      fontSize={3.2}
                      fill="#0f172a"
                      fontWeight={600}
                    >
                      {node.name}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          <div className="map-float--legend synthetic-legend">
            <span className="legend-dot" style={{ background: "#0ea5e9" }} /> Grupo A
            <span className="legend-dot" style={{ background: "#f97316" }} /> Grupo B
            <span className="legend-line" style={{ background: "#f97316" }} /> Arista de corte
          </div>
        </Panel>

        <aside className="synthetic-side">
          <Panel>
            <SectionTitle
              eyebrow="Configuración"
              title="Parámetros del escenario"
              description="El objetivo es idéntico al de la red real; cambia la procedencia de los datos."
            />
            <div className="grid-2">
              <Field label={`Nodos · ${nodes}`}>
                <input className="range" type="range" min={4} max={12} value={nodes} onChange={(e) => setNodes(Number(e.target.value))} />
              </Field>
              <Field label="Semilla">
                <input className="input" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
              </Field>
              <Field label="α · costo">
                <input className="input" type="number" min={0} step={0.1} value={alpha} onChange={(e) => setAlpha(Number(e.target.value))} />
              </Field>
              <Field label="β · balance">
                <input className="input" type="number" min={0.1} step={0.1} value={beta} onChange={(e) => setBeta(Number(e.target.value))} />
              </Field>
            </div>
            <div className="field">
              <span className="field__label">Algoritmos</span>
              <div className="algorithm-grid">
                {ALGORITHMS.map((name) => (
                  <button
                    key={name}
                    type="button"
                    className={`algorithm-toggle ${algorithms.includes(name) ? "is-on" : ""}`}
                    onClick={() =>
                      setAlgorithms((current) =>
                        current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
                      )
                    }
                  >
                    {algorithms.includes(name) ? <Sparkles size={14} /> : <span className="algorithm-toggle__empty" />}
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
              </div>
            </details>
            <button className="button button--primary" onClick={run} disabled={loading || !algorithms.length}>
              {loading ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
              {loading ? "Ejecutando…" : "Ejecutar"}
            </button>
            {error && <ErrorState title="Error de ejecución" message={error} />}
            <div className="warning-strip">
              <TriangleAlert size={15} />
              <span>La red sintética no es una representación del SEIN. Sus valores son supuestos.</span>
            </div>
          </Panel>

          {result && (
            <Panel>
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">Resultados</div>
                  <h3>Métodos</h3>
                </div>
                <Badge tone="green">{result.runs[selectedRun] ? "Listo" : "—"}</Badge>
              </div>
              <div className="run-cards">
                {Object.entries(result.runs).map(([name, run], index) => (
                  <button
                    key={name}
                    className={`run-card ${selectedRun === name ? "is-active" : ""}`}
                    onClick={() => setSelectedRun(name)}
                  >
                    <span className="run-card__top">
                      <span className="run-card__dot" style={{ background: COLORS[index % COLORS.length] }} />
                      <strong>{name}</strong>
                      <Badge tone={isFeasible(run) ? "green" : "amber"}>{isFeasible(run) ? "Factible" : "No factible"}</Badge>
                    </span>
                    <span className="run-card__metrics">
                      <span><small>H</small><strong className="mono">{run.objective === null ? "—" : Number(run.objective).toFixed(5)}</strong></span>
                      <span><small>Corte</small><strong className="mono">{run.cut === null ? "—" : Number(run.cut).toFixed(2)}</strong></span>
                      <span><small>Tiempo</small><strong className="mono">{seconds(run.seconds)}</strong></span>
                    </span>
                  </button>
                ))}
              </div>
              <div className="mini-stats">
                <StatCard label="Mejor H" value={best ? Number(best[1].objective).toFixed(5) : "—"} tone="cyan" icon={<Sparkles size={15} />} />
                <StatCard label="Mejor método" value={best?.[0] ?? "—"} tone="blue" icon={<Zap size={15} />} />
              </div>
              <button className="button button--ghost button--sm" onClick={() => navigate("/comparacion")}>
                <ArrowRight size={14} /> Ver comparación real
              </button>
            </Panel>
          )}
        </aside>
      </div>

      <Panel>
        <div className="panel-heading">
          <div>
            <div className="eyebrow">Recordatorio</div>
            <h3>Separación de capas</h3>
          </div>
          <Info size={16} />
        </div>
        <p className="muted">
          La red sintética usa localidades reales, pero sus enlaces, demanda, generación, capacidad,
          prioridad, vulnerabilidad y posiciones son inventados. No debe confundirse con la capa
          real derivada de OSINERGMIN.
        </p>
      </Panel>
    </div>
  );
}
