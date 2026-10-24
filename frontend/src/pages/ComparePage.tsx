import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Download,
  FlaskConical,
  GitCompareArrows,
  Info,
  Sparkles,
  Trophy,
  Zap,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge, ErrorState, Panel, SectionTitle, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import type { ExperimentBundle, RunResult } from "../lib/types";
import { downloadJson, int, km, pct, seconds } from "../lib/format";

const COLORS = ["#22d3ee", "#3b82f6", "#34d399", "#fbbf24", "#fb7185"];

function feasible(run: RunResult): boolean {
  if (run.feasible !== undefined) return Boolean(run.feasible);
  return Boolean((run.validation as Record<string, unknown> | undefined)?.feasible);
}

export default function ComparePage() {
  const navigate = useNavigate();
  const [bundle, setBundle] = useState<ExperimentBundle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .experiment()
      .then(setBundle)
      .catch(async () => {
        try {
          const response = await fetch(`${import.meta.env.BASE_URL}data/experiment.json`);
          if (!response.ok) throw new Error("No hay artefacto de experimento.");
          setBundle(await response.json());
        } catch (err) {
          setError(String((err as Error)?.message ?? err));
        }
      });
  }, []);

  const runs = useMemo(() => Object.entries(bundle?.runs ?? {}), [bundle]);
  const best = useMemo(() => {
    return [...runs]
      .filter(([, run]) => run.objective !== null && run.objective !== undefined)
      .sort((a, b) => Number(a[1].objective) - Number(b[1].objective))[0];
  }, [runs]);
  const exact = bundle?.runs?.["Exacto"];

  const chartData = runs.map(([name, run]) => ({
    name: name.replace("Kernighan–Lin", "K–L"),
    H: run.objective === null || run.objective === undefined ? null : Number(run.objective.toFixed(5)),
    corte: run.cut === null || run.cut === undefined ? null : Number(run.cut.toFixed(3)),
    ms: Number((run.seconds * 1000).toFixed(0)),
  }));

  const failure = bundle?.extra?.failure_test;

  if (error) {
    return (
      <div className="page-pad">
        <ErrorState
          title="Sin artefacto de comparación"
          message={`${error} Ejecute: python -m scripts.run_real_experiment`}
        />
      </div>
    );
  }
  if (!bundle) {
    return (
      <div className="page-pad loading-page">
        <Spinner label="Cargando experimento reproducible…" />
      </div>
    );
  }

  return (
    <div className="page-pad compare-page">
      <section className="compare-hero">
        <div>
          <div className="eyebrow">Artefacto reproducible</div>
          <h2>Una subred real, cuatro métodos</h2>
          <p>
            {bundle.extra?.experiment ?? "Experimento sobre una subred verificada del SEIN"}. Los
            resultados se generan con semilla fija y se guardan en{" "}
            <code>results/real_subnet_experiment.json</code>.
          </p>
          <div className="button-row">
            <button className="button button--primary" onClick={() => navigate("/optimizacion")}>
              <Sparkles size={15} /> Ejecutar nuevo experimento
            </button>
            <button className="button button--ghost" onClick={() => downloadJson("quantumgrid-experimento.json", bundle)}>
              <Download size={15} /> Descargar JSON
            </button>
          </div>
        </div>
        <div className="compare-hero__stats">
          <StatCard label="Nodos" value={int(bundle.subnet?.nodes.length ?? 0)} tone="cyan" />
          <StatCard label="Conexiones" value={int(bundle.subnet?.edges.length ?? 0)} tone="blue" />
          <StatCard label="Métodos" value={int(runs.length)} tone="green" />
          <StatCard label="Mejor H" value={best ? Number(best[1].objective).toFixed(5) : "—"} tone="amber" />
        </div>
      </section>

      <div className="compare-grid">
        <Panel className="compare-main">
          <SectionTitle
            eyebrow="Resultados"
            title="Comparación de solucionadores"
            description="H es el objetivo adimensional; el corte es una métrica bruta del grafo. Menor H es mejor."
          />
          <div className="run-cards run-cards--wide">
            {runs.map(([name, run], index) => (
              <div className={`run-card ${best?.[0] === name ? "is-best" : ""}`} key={name}>
                <span className="run-card__top">
                  <span className="run-card__dot" style={{ background: COLORS[index % COLORS.length] }} />
                  <strong>{name}</strong>
                  {best?.[0] === name && <Trophy size={14} className="trophy" />}
                  <Badge tone={feasible(run) ? "green" : "amber"}>{feasible(run) ? "Factible" : "No factible"}</Badge>
                </span>
                <span className="run-card__metrics">
                  <span>
                    <small>H</small>
                    <strong className="mono">{run.objective === null ? "—" : Number(run.objective).toFixed(6)}</strong>
                  </span>
                  <span>
                    <small>Corte</small>
                    <strong className="mono">{run.cut === null ? "—" : Number(run.cut).toFixed(3)}</strong>
                  </span>
                  <span>
                    <small>Tiempo</small>
                    <strong className="mono">{seconds(run.seconds)}</strong>
                  </span>
                  <span>
                    <small>Brecha</small>
                    <strong className="mono">
                      {exact && run.objective !== null && exact.objective
                        ? pct((Number(run.objective) - Number(exact.objective)) / Number(exact.objective), 2)
                        : "—"}
                    </strong>
                  </span>
                </span>
              </div>
            ))}
          </div>

          <div className="chart-block">
            <div className="chart-block__head">
              <span>H por método</span>
              <small>Semilla y presupuesto fijos</small>
            </div>
            <div className="chart-block__body">
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
                  <CartesianGrid stroke="rgba(148,163,184,.12)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
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
                  <Bar dataKey="H" radius={[6, 6, 0, 0]}>
                    {chartData.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Panel>

        <div className="compare-side">
          <Panel>
            <div className="panel-heading">
              <div>
                <div className="eyebrow">QAOA</div>
                <h3>Detalle cuántico</h3>
              </div>
              <Badge tone={bundle.runs?.QAOA?.status === "completed" ? "green" : "amber"}>
                {bundle.runs?.QAOA?.status ?? "—"}
              </Badge>
            </div>
            <dl className="detail-list">
              <div>
                <dt>Qubits</dt>
                <dd className="mono">{bundle.runs?.QAOA?.qubits ?? "—"}</dd>
              </div>
              <div>
                <dt>Capas p</dt>
                <dd className="mono">{bundle.runs?.QAOA?.p ?? "—"}</dd>
              </div>
              <div>
                <dt>Shots</dt>
                <dd className="mono">{bundle.runs?.QAOA?.shots ?? "—"}</dd>
              </div>
              <div>
                <dt>Fracción factible</dt>
                <dd className="mono">{pct(bundle.runs?.QAOA?.feasible_fraction)}</dd>
              </div>
              <div>
                <dt>Evaluaciones</dt>
                <dd className="mono">{bundle.runs?.QAOA?.evaluations ?? "—"}</dd>
              </div>
            </dl>
            <div className="info-strip info-strip--muted">
              <FlaskConical size={14} />
              <span>Simulación local con Qiskit Aer. No demuestra ventaja cuántica.</span>
            </div>
          </Panel>

          {failure && (
            <Panel>
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">Prueba de falla</div>
                  <h3>Puente retirado</h3>
                </div>
                <Badge tone="rose">SIMULADO</Badge>
              </div>
              <p className="small">
                {failure.failed_edge.source_name} ↔ {failure.failed_edge.target_name} ·{" "}
                {km(failure.failed_edge.length_km)}
              </p>
              <div className="failure-deltas">
                <div>
                  <small>Aristas</small>
                  <strong className="mono">
                    {failure.before.edges_active} → {failure.after.edges_active}
                  </strong>
                </div>
                <div>
                  <small>Componentes</small>
                  <strong className="mono">
                    {failure.before.components} → {failure.after.components}
                  </strong>
                </div>
                <div>
                  <small>Aislados</small>
                  <strong className="mono">
                    {failure.before.isolated_nodes} → {failure.after.isolated_nodes}
                  </strong>
                </div>
                <div>
                  <small>Longitud activa</small>
                  <strong className="mono">
                    {failure.before.total_length_km_active.toFixed(2)} →{" "}
                    {failure.after.total_length_km_active.toFixed(2)} km
                  </strong>
                </div>
              </div>
              <button className="button button--ghost button--sm" onClick={() => navigate("/fallas")}>
                <Zap size={14} /> Abrir simulador <ArrowRight size={14} />
              </button>
            </Panel>
          )}

          <Panel>
            <div className="panel-heading">
              <div>
                <div className="eyebrow">Lectura correcta</div>
                <h3>Qué no dice este resultado</h3>
              </div>
              <Info size={16} />
            </div>
            <ul className="clean-list">
              <li>No estima energía no suministrada ni pérdida de demanda.</li>
              <li>No modela flujo AC/DC, frecuencia, protecciones ni estabilidad.</li>
              <li>La demanda es un supuesto SIMULADO; la generación se fija en 0.</li>
              <li>Una conexión verificada no certifica operación ni validación COES.</li>
              <li>Los tiempos dependen de la máquina y no son comparables entre hardware.</li>
            </ul>
          </Panel>

          <Panel>
            <div className="panel-heading">
              <div>
                <div className="eyebrow">Reproducir</div>
                <h3>Comando del artefacto</h3>
              </div>
              <BarChart3 size={16} />
            </div>
            <pre className="code-block">{bundle.extra?.command ?? "python -m scripts.run_real_experiment"}</pre>
            <div className="quality-note">
              <Badge tone="cyan">Semilla fija</Badge>
              <Badge tone="blue">IDs originales</Badge>
              <Badge tone="green">Snapshot local</Badge>
            </div>
          </Panel>
        </div>
      </div>

      <Panel>
        <SectionTitle
          eyebrow="Trazabilidad"
          title="Metadatos del experimento"
          description="El artefacto conserva la configuración, la instancia y los resultados completos."
          actions={
            <button className="button button--ghost button--sm" onClick={() => navigate("/fuentes")}>
              <GitCompareArrows size={14} /> Metodología
            </button>
          }
        />
        <div className="meta-grid">
          <div>
            <small>Exportado</small>
            <strong>{bundle.exported_at_utc ?? "—"}</strong>
          </div>
          <div>
            <small>Institución</small>
            <strong>OSINERGMIN</strong>
          </div>
          <div>
            <small>Nodos / aristas</small>
            <strong>
              {bundle.subnet?.nodes.length ?? "—"} / {bundle.subnet?.edges.length ?? "—"}
            </strong>
          </div>
          <div>
            <small>Pesos</small>
            <strong>
              {(bundle.instance?.scenario_metadata as Record<string, any> | undefined)?.weight?.mode ?? "—"}
            </strong>
          </div>
          <div>
            <small>Semilla</small>
            <strong>
              {(bundle.instance?.scenario_metadata as Record<string, any> | undefined)?.seed ?? "—"}
            </strong>
          </div>
          <div>
            <small>Validación COES</small>
            <strong>NO_AUTOMATIZADA</strong>
          </div>
        </div>
      </Panel>
    </div>
  );
}
