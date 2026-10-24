import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  ChevronRight,
  GitBranch,
  Loader2,
  Network,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";
import MapCanvas from "../components/MapCanvas";
import { Badge, ErrorState, Panel, SectionTitle, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import type { ComponentRow, NetworkSummary, Station, Subnet, SubnetPreview } from "../lib/types";
import { int, km, kv } from "../lib/format";
import { voltageColor } from "../lib/colors";

export default function SubnetsPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [summary, setSummary] = useState<NetworkSummary | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [componentIndex, setComponentIndex] = useState(Number(params.get("component") ?? 0));
  const [size, setSize] = useState(Number(params.get("size") ?? 6));
  const [seedNode, setSeedNode] = useState<string>(params.get("seed") ?? "");
  const [preview, setPreview] = useState<SubnetPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.summary(), api.stations()])
      .then(([summaryPayload, stationPayload]) => {
        setSummary(summaryPayload);
        setStations(stationPayload.stations);
      })
      .catch((err) => setError(String(err?.message ?? err)));
  }, []);

  const component: ComponentRow | undefined = summary?.components[componentIndex];
  const componentStations = useMemo(() => {
    if (!component) return [];
    const ids = new Set(component.node_ids);
    return stations.filter((station) => ids.has(station.id)).sort((a, b) => (b.degree ?? 0) - (a.degree ?? 0));
  }, [component, stations]);

  useEffect(() => {
    if (!component) return;
    if (seedNode && !component.node_ids.includes(seedNode)) setSeedNode("");
  }, [component, seedNode]);

  useEffect(() => {
    if (!summary) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      api
        .subnet({
          component_index: componentIndex,
          max_nodes: size,
          seed_node: seedNode || null,
        })
        .then((payload) => {
          if (!cancelled) setPreview(payload);
        })
        .catch((err) => {
          if (!cancelled) {
            setPreview(null);
            setError(String(err?.message ?? err));
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [summary, componentIndex, size, seedNode]);

  const subnet: Subnet | null = preview?.subnet ?? null;
  const query = `component=${componentIndex}&size=${size}${seedNode ? `&seed=${seedNode}` : ""}`;

  if (error && !summary) {
    return (
      <div className="page-pad">
        <ErrorState message={error} />
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="page-pad loading-page">
        <Spinner label="Cargando componentes…" />
      </div>
    );
  }

  return (
    <div className="split-page split-page--wide-aside">
      <div className="split-page__map">
        <MapCanvas mode="subnet" subnet={subnet} layers={{
          verifiedLines: true,
          unverifiedLines: false,
          stations: true,
          generation: false,
          labels: true,
        }} />
        {loading && (
          <div className="map-float map-float--center">
            <Spinner label="Construyendo subred conectada…" />
          </div>
        )}
        {error && !loading && (
          <div className="map-float map-float--center">
            <ErrorState title="No se pudo construir la subred" message={error} />
          </div>
        )}
        <div className="map-float map-float--bottom">
          <div className="map-float__row">
            <Badge tone="cyan">{subnet?.nodes.length ?? 0} nodos</Badge>
            <Badge tone="blue">{subnet?.edges.length ?? 0} conexiones</Badge>
            <Badge tone="green">{subnet ? km(subnet.stats.total_length_km) : "—"}</Badge>
            <Badge tone="amber">{subnet?.stats.bridges.length ?? 0} puentes</Badge>
          </div>
        </div>
      </div>

      <aside className="split-page__aside">
        <Panel>
          <SectionTitle
            eyebrow="Constructor de subredes"
            title="Componente conectada"
            description="La subred se extrae del grafo verificado. No se añaden aristas por proximidad."
            actions={
              <button
                className="icon-button"
                onClick={() => {
                  setLoading(true);
                  api
                    .subnet({ component_index: componentIndex, max_nodes: size, seed_node: seedNode || null })
                    .then(setPreview)
                    .catch((err) => setError(String(err?.message ?? err)))
                    .finally(() => setLoading(false));
                }}
                title="Recalcular"
              >
                <RefreshCw size={15} />
              </button>
            }
          />

          <label className="field">
            <span className="field__label">Componente</span>
            <select
              className="select"
              value={componentIndex}
              onChange={(event) => {
                setComponentIndex(Number(event.target.value));
                setSeedNode("");
              }}
            >
              {summary.components.map((row) => (
                <option key={row.index} value={row.index}>
                  {row.label} · {row.nodes} nodos · {row.edges} aristas
                </option>
              ))}
            </select>
            {component && (
              <span className="field__hint">
                {component.departments.join(", ") || "Sin departamento"} ·{" "}
                {component.voltages_kv.map((value) => `${value} kV`).join(", ")}
              </span>
            )}
          </label>

          <div className="field">
            <span className="field__label">Tamaño de la subred · {size} nodos</span>
            <input
              type="range"
              min={2}
              max={12}
              step={1}
              value={size}
              onChange={(event) => setSize(Number(event.target.value))}
              className="range"
            />
            <span className="field__hint">
              {component && component.nodes < size
                ? `La componente solo tiene ${component.nodes} nodos; se usará el máximo disponible.`
                : "El solver acepta hasta 12 nodos."}
            </span>
          </div>

          <label className="field">
            <span className="field__label">Semilla (opcional)</span>
            <select className="select" value={seedNode} onChange={(event) => setSeedNode(event.target.value)}>
              <option value="">Selección automática (mayor grado)</option>
              {componentStations.map((station) => (
                <option key={station.id} value={station.id}>
                  {station.name} · {station.degree ?? 0} conexiones
                </option>
              ))}
            </select>
          </label>

          <div className="button-row">
            <button className="button button--primary" onClick={() => navigate(`/optimizacion?${query}`)}>
              <Sparkles size={15} /> Optimizar esta subred <ArrowRight size={14} />
            </button>
            <button className="button button--ghost" onClick={() => navigate(`/fallas?${query}`)}>
              <Zap size={15} /> Simular falla
            </button>
          </div>
        </Panel>

        {subnet && (
          <>
            <Panel>
              <div className="mini-stats">
                <StatCard label="Nodos" value={int(subnet.stats.nodes)} tone="cyan" icon={<Network size={15} />} />
                <StatCard label="Aristas" value={int(subnet.stats.edges)} tone="blue" icon={<GitBranch size={15} />} />
                <StatCard label="Longitud" value={km(subnet.stats.total_length_km)} tone="green" icon={<Boxes size={15} />} />
                <StatCard label="Puentes" value={int(subnet.stats.bridges.length)} tone="amber" icon={<Zap size={15} />} />
              </div>
              <div className="info-strip">
                <Badge tone={subnet.selection.truncated ? "amber" : "green"}>
                  {subnet.selection.truncated ? "Truncada" : "Completa"}
                </Badge>
                <span>{subnet.selection.message}</span>
              </div>
              <div className="info-strip info-strip--muted">
                <span>
                  Pool de la componente: <strong>{subnet.selection.pool_nodes}</strong> nodos. Semilla:{" "}
                  <strong>
                    {subnet.selection.seed_node
                      ? subnet.nodes.find((node) => node.id === subnet.selection.seed_node)?.name ??
                        subnet.selection.seed_node
                      : "automática"}
                  </strong>
                  .
                </span>
              </div>
            </Panel>

            <Panel padding="none">
              <div className="panel-heading panel-heading--pad">
                <div>
                  <div className="eyebrow">Trazabilidad</div>
                  <h3>Conexiones de la subred</h3>
                </div>
                <Badge tone="cyan">Verificadas</Badge>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Desde</th>
                      <th>Hasta</th>
                      <th>kV</th>
                      <th>km</th>
                      <th>Líneas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subnet.edges.map((edge) => (
                      <tr key={edge.id}>
                        <td>{edge.source_name}</td>
                        <td>{edge.target_name}</td>
                        <td>
                          <span className="kv-cell">
                            <span
                              className="chip__dot"
                              style={{ background: voltageColor(edge.voltage_kv) }}
                            />
                            {kv(edge.voltage_kv)}
                          </span>
                        </td>
                        <td className="mono">{edge.length_km.toFixed(2)}</td>
                        <td>{edge.line_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>

            <Panel>
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">Topología</div>
                  <h3>Puentes detectados</h3>
                </div>
                <Badge tone="amber">{subnet.stats.bridges.length}</Badge>
              </div>
              <p className="muted small">
                Un puente separa la subred si falla. Úselo en el simulador para comparar antes/después.
              </p>
              <div className="bridge-list">
                {subnet.stats.bridges.slice(0, 6).map(([a, b]) => {
                  const edge = subnet.edges.find(
                    (row) => (row.source === a && row.target === b) || (row.source === b && row.target === a),
                  );
                  return (
                    <button
                      key={`${a}-${b}`}
                      className="bridge-row"
                      onClick={() => navigate(`/fallas?${query}&edge=${edge?.id ?? ""}`)}
                    >
                      <Zap size={14} />
                      <span>
                        {edge ? `${edge.source_name} ↔ ${edge.target_name}` : `${a} ↔ ${b}`}
                      </span>
                      <span className="mono">{edge ? km(edge.length_km) : ""}</span>
                      <ChevronRight size={14} />
                    </button>
                  );
                })}
                {!subnet.stats.bridges.length && <p className="muted">Esta subred no contiene puentes.</p>}
              </div>
            </Panel>
          </>
        )}
        {loading && !subnet && (
          <Panel>
            <div className="loading-block">
              <Loader2 size={24} className="spin" />
              <span>Construyendo subred…</span>
            </div>
          </Panel>
        )}
      </aside>
    </div>
  );
}
