import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Building2,
  Crosshair,
  Filter,
  GitBranch,
  Network,
  RotateCcw,
  Search,
  Zap,
} from "lucide-react";
import MapCanvas, { type LayerState, type MapFocus } from "../components/MapCanvas";
import { Badge, ErrorState, Panel, SectionTitle, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import type { NetworkSummary } from "../lib/types";
import { STATUS_LABELS, VOLTAGE_ORDER, voltageColor } from "../lib/colors";
import { int, km, kv } from "../lib/format";

const LAYERS: LayerState = {
  verifiedLines: true,
  unverifiedLines: true,
  stations: true,
  generation: true,
  labels: true,
};

export default function NetworkPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<NetworkSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [voltages, setVoltages] = useState<number[]>([]);
  const [department, setDepartment] = useState("");
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.summary().then(setSummary).catch((err) => setError(String(err?.message ?? err)));
  }, []);

  const departments = useMemo(
    () => (summary ? Object.keys(summary.department_counts).sort((a, b) => a.localeCompare(b)) : []),
    [summary],
  );

  const stations = useMemo(() => {
    if (!summary) return [];
    const term = query.trim().toUpperCase();
    return summary.top_stations.filter(
      (station) =>
        (!term || station.name.toUpperCase().includes(term)) &&
        (!voltages.length || voltages.includes(Number(station.voltage_kv))) &&
        (!department || station.department === department),
    );
  }, [summary, query, voltages, department]);

  if (error) {
    return (
      <div className="page-pad">
        <ErrorState message={error} />
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="page-pad loading-page">
        <Spinner label="Cargando red nacional…" />
      </div>
    );
  }

  const statusEntries = Object.entries(summary.line_status_counts).sort((a, b) => b[1] - a[1]);

  return (
    <div className="split-page">
      <div className="split-page__map">
        <MapCanvas
          layers={LAYERS}
          voltages={voltages}
          departments={department ? [department] : []}
          focus={focus}
          resetKey={resetKey}
        />
        <div className="map-float map-float--top">
          <div className="map-float__row">
            <div className="map-float__search">
              <Search size={15} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Filtrar estaciones destacadas…"
              />
            </div>
            <button className="button button--ghost button--sm" onClick={() => setResetKey((v) => v + 1)}>
              <RotateCcw size={14} /> Perú
            </button>
          </div>
          <div className="chip-row chip-row--scroll">
            <button className={`chip ${!voltages.length ? "is-active" : ""}`} onClick={() => setVoltages([])}>
              Todas
            </button>
            {VOLTAGE_ORDER.filter((value) => summary.voltage_counts.stations[String(value)]).map((value) => (
              <button
                key={value}
                className={`chip ${voltages.includes(value) ? "is-active" : ""}`}
                onClick={() =>
                  setVoltages((current) =>
                    current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
                  )
                }
              >
                <span className="chip__dot" style={{ background: voltageColor(value) }} />
                {value} kV
              </button>
            ))}
          </div>
        </div>
      </div>

      <aside className="split-page__aside">
        <Panel>
          <SectionTitle
            eyebrow="Snapshot nacional"
            title="Red verificada"
            description="La geometría oficial se muestra completa; solo las conexiones con extremos resueltos forman el grafo."
            actions={
              <button className="button button--primary button--sm" onClick={() => navigate("/subredes")}>
                <GitBranch size={14} /> Subredes
              </button>
            }
          />
          <div className="mini-stats">
            <StatCard label="Subestaciones" value={int(summary.counts.stations)} tone="cyan" icon={<Building2 size={15} />} />
            <StatCard label="En grafo" value={int(summary.counts.stations_in_verified_graph)} tone="blue" icon={<Network size={15} />} />
            <StatCard label="Conexiones" value={int(summary.counts.edges)} tone="green" icon={<Zap size={15} />} />
            <StatCard label="Componentes" value={int(summary.counts.components_with_edges)} tone="amber" icon={<GitBranch size={15} />} />
          </div>
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Filtros</div>
              <h3>Departamento</h3>
            </div>
            <Filter size={16} />
          </div>
          <select className="select" value={department} onChange={(event) => setDepartment(event.target.value)}>
            <option value="">Todo el Perú</option>
            {departments.map((name) => (
              <option key={name} value={name}>
                {name} · {summary.department_counts[name]} estaciones
              </option>
            ))}
          </select>
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Estaciones destacadas</div>
              <h3>Mayor grado verificado</h3>
            </div>
            <span className="mono muted">{stations.length}</span>
          </div>
          <div className="station-list">
            {stations.map((station) => (
              <button
                key={station.id}
                className="station-row"
                onClick={() => setFocus({ lon: station.lon, lat: station.lat, zoom: 10.5 })}
              >
                <span className="station-row__kv" style={{ background: voltageColor(station.voltage_kv) }}>
                  {station.voltage_kv ?? "?"}
                </span>
                <span className="station-row__copy">
                  <strong>{station.name}</strong>
                  <small>
                    {station.department ?? "Sin departamento"} · {station.degree} conexiones
                  </small>
                </span>
                <Crosshair size={14} className="station-row__icon" />
              </button>
            ))}
            {!stations.length && <p className="muted">No hay estaciones con esos filtros.</p>}
          </div>
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Calidad topológica</div>
              <h3>Estado de líneas</h3>
            </div>
          </div>
          <div className="status-bars">
            {statusEntries.map(([status, count]) => (
              <div className="status-bar" key={status}>
                <div className="status-bar__top">
                  <span>{STATUS_LABELS[status] ?? status}</span>
                  <strong className="mono">{count}</strong>
                </div>
                <div className="status-bar__track">
                  <span
                    style={{
                      width: `${(count / summary.counts.lines) * 100}%`,
                      background: status === "verified" ? "#0891b2" : "#94a3b8",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="quality-note">
            <Badge tone="cyan">618 verificadas</Badge>
            <Badge tone="slate">359 no verificadas</Badge>
            <Badge tone="rose">0 COES</Badge>
          </div>
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Mayor longitud</div>
              <h3>Componentes conectadas</h3>
            </div>
            <button className="text-button" onClick={() => navigate("/subredes")}>
              Ver todas <ArrowRight size={13} />
            </button>
          </div>
          <div className="component-list">
            {summary.components.slice(0, 5).map((component) => (
              <button
                key={component.index}
                className="component-row"
                onClick={() => navigate(`/subredes?component=${component.index}`)}
              >
                <span className="component-row__index">{String(component.index + 1).padStart(2, "0")}</span>
                <span className="component-row__copy">
                  <strong>
                    {component.nodes} nodos · {component.edges} aristas
                  </strong>
                  <small>{component.sample_names.join(" · ")}</small>
                </span>
                <span className="component-row__length mono">{km(component.total_length_km)}</span>
              </button>
            ))}
          </div>
        </Panel>
      </aside>
    </div>
  );
}
