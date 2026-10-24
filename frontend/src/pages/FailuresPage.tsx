import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Download,
  GitCompareArrows,
  Info,
  Loader2,
  Play,
  ShieldAlert,
  Sparkles,
  TriangleAlert,
  Zap,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import MapCanvas from "../components/MapCanvas";
import { Badge, ErrorState, Panel, SectionTitle, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import type { FailureResponse, NetworkSummary, SubnetPreview } from "../lib/types";
import { downloadJson, int, km } from "../lib/format";

function deltaLabel(value: number | null | undefined, unit = ""): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value}${unit}`;
}

export default function FailuresPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [summary, setSummary] = useState<NetworkSummary | null>(null);
  const [componentIndex, setComponentIndex] = useState(Number(params.get("component") ?? 0));
  const [size, setSize] = useState(Number(params.get("size") ?? 6));
  const [seedNode, setSeedNode] = useState(params.get("seed") ?? "");
  const [preview, setPreview] = useState<SubnetPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [selectedEdges, setSelectedEdges] = useState<string[]>(
    params.get("edge") ? [params.get("edge") as string] : [],
  );
  const [result, setResult] = useState<FailureResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.summary().then(setSummary).catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    setResult(null);
    api
      .subnet({ component_index: componentIndex, max_nodes: size, seed_node: seedNode || null })
      .then((payload) => {
        if (!cancelled) {
          setPreview(payload);
          setSelectedEdges((current) => current.filter((id) => payload.subnet.edges.some((edge) => edge.id === id)));
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String((err as Error)?.message ?? err));
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [componentIndex, size, seedNode]);

  const subnet = preview?.subnet ?? null;
  const bridgeIds = useMemo(() => new Set(preview?.bridge_edges.map((edge) => edge.id) ?? []), [preview]);

  const chartData = useMemo(() => {
    if (!result) return [];
    return [
      { name: "Antes", aristas: result.before.edges_active, componentes: result.before.components, aislados: result.before.isolated_nodes },
      { name: "Después", aristas: result.after.edges_active, componentes: result.after.components, aislados: result.after.isolated_nodes },
    ];
  }, [result]);

  async function applyFailure() {
    if (!selectedEdges.length) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.failure({
        component_index: componentIndex,
        max_nodes: size,
        seed_node: seedNode || null,
        failed_edge_ids: selectedEdges,
      });
      setResult(response);
    } catch (err) {
      setError(String((err as Error)?.message ?? err));
    } finally {
      setLoading(false);
    }
  }

  if (!summary) {
    return (
      <div className="page-pad loading-page">
        <Spinner label="Preparando simulador…" />
      </div>
    );
  }

  const visibleSubnet = result?.failed_subnet ?? subnet;

  return (
    <div className="split-page split-page--wide-aside">
      <div className="split-page__map">
        <MapCanvas
          mode="subnet"
          subnet={visibleSubnet}
          failedEdgeIds={result ? result.failed_edges.map((edge) => edge.id) : selectedEdges}
          layers={{
            verifiedLines: true,
            unverifiedLines: false,
            stations: true,
            generation: false,
            labels: true,
          }}
        />
        {previewLoading && (
          <div className="map-float map-float--center">
            <Spinner label="Construyendo subred…" />
          </div>
        )}
        <div className="map-float map-float--top map-float--legend">
          <span className="legend-dot" style={{ background: "#0891b2" }} /> Conexión activa
          <span className="legend-dot" style={{ background: "#f43f5e" }} /> Falla simulada
          <span className="legend-dot" style={{ background: "#94a3b8" }} /> Red nacional
        </div>
        <div className="map-float map-float--bottom">
          <div className="map-float__row">
            <Badge tone="cyan">{visibleSubnet?.nodes.length ?? 0} nodos</Badge>
            <Badge tone={result ? "rose" : "blue"}>{result ? result.after.edges_active : visibleSubnet?.edges.length ?? 0} aristas activas</Badge>
            <Badge tone="amber">{selectedEdges.length} fallas</Badge>
          </div>
        </div>
      </div>

      <aside className="split-page__aside">
        <Panel>
          <SectionTitle
            eyebrow="Escenario topológico"
            title="Simulador de fallas"
            description="Retire una o más conexiones y compare la topología antes/después. No se estima energía no suministrada."
          />

          <div className="grid-2">
            <label className="field">
              <span className="field__label">Componente</span>
              <select className="select" value={componentIndex} onChange={(event) => setComponentIndex(Number(event.target.value))}>
                {summary.components.map((row) => (
                  <option key={row.index} value={row.index}>
                    {row.label} · {row.nodes} nodos
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Nodos · {size}</span>
              <input className="range" type="range" min={2} max={12} value={size} onChange={(event) => setSize(Number(event.target.value))} />
            </label>
          </div>

          {!!preview?.bridge_edges.length && (
            <div className="field">
              <span className="field__label">Puentes recomendados</span>
              <div className="failure-options">
                {preview.bridge_edges.map((edge) => (
                  <label key={edge.id} className="check-row check-row--bridge">
                    <input
                      type="checkbox"
                      checked={selectedEdges.includes(edge.id)}
                      onChange={(event) =>
                        setSelectedEdges((current) =>
                          event.target.checked ? [...current, edge.id] : current.filter((id) => id !== edge.id),
                        )
                      }
                    />
                    <span>
                      {edge.source_name} ↔ {edge.target_name}
                      <small>
                        {km(edge.length_km)} · {edge.voltage_kv ?? "s/t"} kV · puente
                      </small>
                    </span>
                    <ShieldAlert size={14} />
                  </label>
                ))}
              </div>
            </div>
          )}

          {subnet && (
            <details className="config-details" open={!preview?.bridge_edges.length}>
              <summary>
                <Zap size={15} /> Todas las conexiones ({subnet.edges.length})
              </summary>
              <div className="failure-options failure-options--scroll">
                {subnet.edges.map((edge) => (
                  <label key={edge.id} className="check-row">
                    <input
                      type="checkbox"
                      checked={selectedEdges.includes(edge.id)}
                      onChange={(event) =>
                        setSelectedEdges((current) =>
                          event.target.checked ? [...current, edge.id] : current.filter((id) => id !== edge.id),
                        )
                      }
                    />
                    <span>
                      {edge.source_name} ↔ {edge.target_name}
                      <small>
                        {km(edge.length_km)} · {edge.voltage_kv ?? "s/t"} kV
                        {bridgeIds.has(edge.id) ? " · puente" : ""}
                      </small>
                    </span>
                  </label>
                ))}
              </div>
            </details>
          )}

          <div className="button-row">
            <button className="button button--primary" onClick={applyFailure} disabled={!selectedEdges.length || loading || !subnet}>
              {loading ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
              {loading ? "Simulando…" : "Aplicar falla"}
            </button>
            <button className="button button--ghost" onClick={() => setSelectedEdges([])}>
              Limpiar selección
            </button>
          </div>

          {error && <ErrorState title="No se pudo simular" message={error} />}

          <div className="warning-strip">
            <TriangleAlert size={15} />
            <span>
              Una falla es un escenario topológico. No modela protecciones, flujo, frecuencia ni
              re-despacho.
            </span>
          </div>
        </Panel>

        {result && (
          <>
            <Panel>
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">Antes / después</div>
                  <h3>Impacto topológico</h3>
                </div>
                <button className="icon-button" onClick={() => downloadJson(`energyquantum-falla-${componentIndex}-${size}.json`, result)} title="Exportar JSON">
                  <Download size={15} />
                </button>
              </div>
              <div className="before-after">
                <div className="before-after__col">
                  <span className="before-after__label">Antes</span>
                  <strong className="mono">{result.before.edges_active}</strong>
                  <small>aristas activas</small>
                  <strong className="mono">{result.before.components}</strong>
                  <small>componentes</small>
                  <strong className="mono">{result.before.isolated_nodes}</strong>
                  <small>nodos aislados</small>
                </div>
                <div className="before-after__arrow">
                  <ArrowRight size={18} />
                </div>
                <div className="before-after__col before-after__col--after">
                  <span className="before-after__label">Después</span>
                  <strong className="mono">{result.after.edges_active}</strong>
                  <small>aristas activas</small>
                  <strong className="mono">{result.after.components}</strong>
                  <small>componentes</small>
                  <strong className="mono">{result.after.isolated_nodes}</strong>
                  <small>nodos aislados</small>
                </div>
              </div>
              <div className="mini-stats">
                <StatCard
                  label="Δ aristas"
                  value={deltaLabel(result.comparison.delta.edges_active)}
                  tone="rose"
                  icon={<Zap size={15} />}
                />
                <StatCard
                  label="Δ componentes"
                  value={deltaLabel(result.comparison.delta.components)}
                  tone="amber"
                  icon={<GitCompareArrows size={15} />}
                />
                <StatCard
                  label="Δ longitud activa"
                  value={deltaLabel(result.comparison.delta.total_length_km_active, " km")}
                  tone="blue"
                  icon={<Sparkles size={15} />}
                />
                <StatCard
                  label="Nodos aislados"
                  value={int(result.after.isolated_nodes)}
                  tone="rose"
                  icon={<ShieldAlert size={15} />}
                />
              </div>
              <div className="chart-block__body">
                <ResponsiveContainer width="100%" height={190}>
                  <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
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
                    <Bar dataKey="aristas" fill="#0891b2" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="componentes" fill="#fbbf24" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="aislados" fill="#fb7185" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="info-strip info-strip--muted">
                <Info size={14} />
                <span>{result.comparison.note}</span>
              </div>
            </Panel>

            <Panel>
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">Conexiones retiradas</div>
                  <h3>{result.failed_edges.length} fallas aplicadas</h3>
                </div>
                <Badge tone="rose">SIMULADO</Badge>
              </div>
              <div className="failed-list">
                {result.failed_edges.map((edge) => (
                  <div className="failed-row" key={edge.id}>
                    <Zap size={14} />
                    <span>
                      <strong>
                        {edge.source_name} ↔ {edge.target_name}
                      </strong>
                      <small className="mono">{edge.id}</small>
                    </span>
                    <span className="mono">{km(edge.length_km)}</span>
                  </div>
                ))}
              </div>
              <div className="button-row">
                <button className="button button--primary button--sm" onClick={() => navigate(`/optimizacion?component=${componentIndex}&size=${size}${seedNode ? `&seed=${seedNode}` : ""}`)}>
                  <Sparkles size={14} /> Optimizar esta subred
                </button>
                <button className="button button--ghost button--sm" onClick={() => navigate("/comparacion")}>
                  <GitCompareArrows size={14} /> Comparación
                </button>
              </div>
            </Panel>
          </>
        )}
      </aside>
    </div>
  );
}
