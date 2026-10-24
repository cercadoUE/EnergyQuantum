import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  Building2,
  Compass,
  Crosshair,
  Database,
  Layers3,
  MapPin,
  Radio,
  RotateCcw,
  Sparkles,
  X,
  Zap,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import MapCanvas, { type LayerState, type MapFocus } from "../components/MapCanvas";
import { Badge, ErrorState, Panel, Spinner, StatCard, Toggle } from "../components/ui";
import { api } from "../lib/api";
import type { NetworkSummary, Station } from "../lib/types";
import { VOLTAGE_ORDER, voltageColor } from "../lib/colors";
import { dateLabel, int, km, kv } from "../lib/format";

const DEFAULT_LAYERS: LayerState = {
  verifiedLines: true,
  unverifiedLines: true,
  stations: true,
  generation: true,
  labels: true,
};

export default function MapPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [summary, setSummary] = useState<NetworkSummary | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);
  const [voltages, setVoltages] = useState<number[]>([]);
  const [department, setDepartment] = useState("");
  const [cursor, setCursor] = useState<{ lon: number; lat: number } | null>(null);
  const [zoom, setZoom] = useState(5.05);
  const [selected, setSelected] = useState<Station | null>(null);
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [layersOpen, setLayersOpen] = useState(false);
  const [heroOpen, setHeroOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth > 720,
  );

  function computeFitPadding(heroVisible: boolean) {
    const width = typeof window === "undefined" ? 1440 : window.innerWidth;
    if (width >= 1320) return { top: 40, right: 350, bottom: 70, left: 510 };
    if (width >= 1120) return { top: 40, right: 320, bottom: 70, left: 470 };
    if (width >= 980) return { top: 40, right: 300, bottom: 70, left: 440 };
    if (width < 720) return { top: 24, right: 20, bottom: 56, left: 20 };
    return heroVisible
      ? { top: 24, right: 20, bottom: 56, left: Math.min(470, Math.round(width * 0.52)) }
      : { top: 24, right: 20, bottom: 56, left: 20 };
  }

  const [fitPadding, setFitPadding] = useState(() => computeFitPadding(heroOpen));

  function toggleHero() {
    const next = !heroOpen;
    setHeroOpen(next);
    setFitPadding(computeFitPadding(next));
    setResetKey((value) => value + 1);
  }

  useEffect(() => {
    Promise.all([api.summary(), api.stations()])
      .then(([summaryPayload, stationPayload]) => {
        setSummary(summaryPayload);
        setStations(stationPayload.stations);
      })
      .catch((err) => setError(String(err?.message ?? err)));
  }, []);

  useEffect(() => {
    const id = params.get("station");
    if (!id || !stations.length) return;
    const station = stations.find((row) => row.id === id);
    if (station) {
      setSelected(station);
      setFocus({ lon: station.lon, lat: station.lat, zoom: 10.5 });
    }
  }, [params, stations]);

  const departments = useMemo(() => {
    if (!summary) return [];
    return Object.keys(summary.department_counts).sort((a, b) => a.localeCompare(b));
  }, [summary]);

  const activeDepartment = department ? [department] : [];

  function toggleVoltage(value: number) {
    setVoltages((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  }

  function resetView() {
    setVoltages([]);
    setDepartment("");
    setSelected(null);
    setLayers(DEFAULT_LAYERS);
    setFocus(null);
    setResetKey((value) => value + 1);
  }

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
        <Spinner label="Cargando snapshot del SEIN…" />
      </div>
    );
  }

  return (
    <div className="map-page">
      <MapCanvas
        mode="national"
        layers={layers}
        voltages={voltages}
        departments={activeDepartment}
        focus={focus}
        resetKey={resetKey}
        fitPadding={fitPadding}
        onStationSelect={(station) => {
          const match = stations.find((row) => row.id === station.id);
          setSelected(match ?? (station as unknown as Station));
          setFocus({ lon: station.lon, lat: station.lat, zoom: 10.5 });
        }}
        onCursor={setCursor}
        onZoom={setZoom}
      />

      <section className={`map-hero ${heroOpen ? "" : "is-hidden"}`} aria-hidden={!heroOpen}>
        <button
          className="map-hero__collapse"
          onClick={toggleHero}
          aria-label="Ocultar resumen"
          title="Ocultar resumen"
        >
          <ChevronUp size={15} />
        </button>
        <div className="map-hero__eyebrow">
          <span className="status-dot" />
          SEIN · SISTEMA ELÉCTRICO INTERCONECTADO NACIONAL
        </div>
        <h1>
          La red eléctrica del Perú,
          <br />
          <em>en una sola vista.</em>
        </h1>
        <p>
          {int(summary.counts.stations)} subestaciones y {int(summary.counts.lines)} líneas
          oficiales. Solo las conexiones con extremos explícitos resueltos se convierten en
          aristas del grafo.
        </p>

        <div className="map-hero__stats">
          <StatCard
            label="Subestaciones"
            value={int(summary.counts.stations)}
            hint={`${int(summary.counts.stations_in_verified_graph)} en el grafo verificado`}
            tone="cyan"
            icon={<Building2 size={16} />}
          />
          <StatCard
            label="Líneas verificadas"
            value={int(summary.counts.lines_verified)}
            hint={`${int(summary.counts.lines_unverified)} no verificadas`}
            tone="blue"
            icon={<Radio size={16} />}
          />
          <StatCard
            label="Conexiones agregadas"
            value={int(summary.counts.edges)}
            hint="Aristas con extremos explícitos"
            tone="green"
            icon={<Zap size={16} />}
          />
          <StatCard
            label="Componentes con aristas"
            value={int(summary.counts.components_with_edges)}
            hint={`Mayor: ${int(summary.quality.largest_component_nodes)} nodos`}
            tone="amber"
            icon={<Boxes size={16} />}
          />
        </div>

        <div className="map-hero__actions">
          <button className="button button--primary" onClick={() => navigate("/subredes")}>
            <Boxes size={16} /> Explorar subredes <ArrowRight size={15} />
          </button>
          <button className="button button--ghost" onClick={() => navigate("/optimizacion")}>
            <Sparkles size={16} /> Optimizar red
          </button>
        </div>

        <div className="map-hero__foot">
          <Database size={13} />
          <span>
            {summary.source.institution} · snapshot {dateLabel(summary.generated_at_utc)} ·{" "}
            {int(summary.counts.coes_validated_edges)} aristas validadas por COES
          </span>
        </div>
      </section>

      {!heroOpen && (
        <button className="map-hero-pill" onClick={toggleHero} aria-label="Mostrar resumen del SEIN">
          <span className="status-dot" />
          SEIN · Resumen de la red
          <ChevronDown size={14} />
        </button>
      )}

      <button
        className="map-layers-toggle"
        onClick={() => setLayersOpen(true)}
        aria-label="Abrir control de capas"
      >
        <Layers3 size={16} /> Capas
      </button>

      {layersOpen && (
        <button
          className="map-layers-backdrop"
          aria-label="Cerrar control de capas"
          onClick={() => setLayersOpen(false)}
        />
      )}

      <aside className={`map-layers ${layersOpen ? "is-open" : ""}`}>
        <div className="map-layers__head">
          <div>
            <div className="eyebrow">Control de capas</div>
            <h3>Mapa nacional</h3>
          </div>
          <div className="map-layers__head-actions">
            <button className="icon-button" onClick={resetView} title="Restablecer vista">
              <RotateCcw size={16} />
            </button>
            <button
              className="icon-button map-layers__close"
              onClick={() => setLayersOpen(false)}
              title="Cerrar"
              aria-label="Cerrar control de capas"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="map-layers__section">
          <Toggle
            checked={layers.verifiedLines}
            onChange={(value) => setLayers({ ...layers, verifiedLines: value })}
            label="Líneas verificadas"
            description="Extremos explícitos resueltos"
            color="#0891b2"
          />
          <Toggle
            checked={layers.unverifiedLines}
            onChange={(value) => setLayers({ ...layers, unverifiedLines: value })}
            label="Líneas no verificadas"
            description="Geometría oficial, sin arista"
            color="#94a3b8"
          />
          <Toggle
            checked={layers.stations}
            onChange={(value) => setLayers({ ...layers, stations: value })}
            label="Subestaciones"
            description={`${int(summary.counts.stations)} puntos`}
            color="#2563eb"
          />
          <Toggle
            checked={layers.generation}
            onChange={(value) => setLayers({ ...layers, generation: value })}
            label="Generación"
            description={`${int(summary.counts.generation)} centrales`}
            color="#10b981"
          />
          <Toggle
            checked={layers.labels}
            onChange={(value) => setLayers({ ...layers, labels: value })}
            label="Etiquetas"
            description="Subestaciones ≥ 220 kV"
            color="#0f172a"
          />
        </div>

        <div className="map-layers__section">
          <div className="map-layers__label">Tensión</div>
          <div className="chip-row">
            <button
              className={`chip ${voltages.length === 0 ? "is-active" : ""}`}
              onClick={() => setVoltages([])}
            >
              Todas
            </button>
            {VOLTAGE_ORDER.filter((value) => summary.voltage_counts.lines[String(value)]).map(
              (value) => (
                <button
                  key={value}
                  className={`chip ${voltages.includes(value) ? "is-active" : ""}`}
                  onClick={() => toggleVoltage(value)}
                >
                  <span className="chip__dot" style={{ background: voltageColor(value) }} />
                  {value} kV
                </button>
              ),
            )}
          </div>
        </div>

        <div className="map-layers__section">
          <label className="map-layers__label" htmlFor="department-filter">
            Departamento
          </label>
          <select
            id="department-filter"
            className="select"
            value={department}
            onChange={(event) => setDepartment(event.target.value)}
          >
            <option value="">Todo el Perú</option>
            {departments.map((name) => (
              <option key={name} value={name}>
                {name} · {summary.department_counts[name]}
              </option>
            ))}
          </select>
        </div>

        <div className="map-layers__legend">
          <div className="map-layers__label">Leyenda</div>
          <div className="legend-row">
            <span className="legend-line legend-line--verified" />
            <span>Línea verificada</span>
          </div>
          <div className="legend-row">
            <span className="legend-line legend-line--unverified" />
            <span>Línea no verificada</span>
          </div>
          <div className="legend-row">
            <span className="legend-dot" style={{ background: "#2563eb" }} />
            <span>Subestación</span>
          </div>
          <div className="legend-row">
            <span className="legend-dot legend-dot--gen" />
            <span>Central de generación</span>
          </div>
        </div>
      </aside>

      {selected && (
        <aside className="station-drawer">
          <div className="station-drawer__head">
            <div>
              <div className="eyebrow">Subestación</div>
              <h3>{selected.name}</h3>
            </div>
            <button className="icon-button" onClick={() => setSelected(null)} aria-label="Cerrar">
              <X size={16} />
            </button>
          </div>
          <div className="station-drawer__badges">
            <Badge tone="cyan">{kv(selected.voltage_kv)}</Badge>
            <Badge tone="slate">{selected.department ?? "Sin departamento"}</Badge>
            <Badge tone="green">{selected.degree ?? 0} conexiones</Badge>
          </div>
          <dl className="detail-list">
            <div>
              <dt>Empresa</dt>
              <dd>{selected.company ?? "—"}</dd>
            </div>
            <div>
              <dt>ID original</dt>
              <dd className="mono">{selected.id}</dd>
            </div>
            <div>
              <dt>Coordenadas</dt>
              <dd className="mono">
                {selected.lon.toFixed(5)}, {selected.lat.toFixed(5)}
              </dd>
            </div>
            <div>
              <dt>Procedencia</dt>
              <dd>
                <Badge tone="cyan">OFICIAL</Badge> <Badge tone="blue">DERIVADO</Badge>
              </dd>
            </div>
          </dl>
          <div className="station-drawer__actions">
            <button
              className="button button--primary button--sm"
              onClick={() => setFocus({ lon: selected.lon, lat: selected.lat, zoom: 11.5 })}
            >
              <Crosshair size={14} /> Centrar
            </button>
            <button
              className="button button--ghost button--sm"
              onClick={() => navigate(`/subredes?seed=${selected.id}`)}
            >
              <Compass size={14} /> Subred cercana
            </button>
          </div>
          <div className="station-drawer__note">
            <MapPin size={13} />
            <span>
              La identidad de estación es derivada. Una conexión verificada no certifica
              suministro ni operación.
            </span>
          </div>
        </aside>
      )}

      <div className="map-statusbar">
        <div className="map-statusbar__coords mono">
          <Crosshair size={13} />
          {cursor
            ? `LON ${cursor.lon.toFixed(5)} · LAT ${cursor.lat.toFixed(5)}`
            : "Mueva el cursor sobre el mapa"}
        </div>
        <div className="map-statusbar__mid">
          <span className="status-dot status-dot--green" />
          {int(summary.counts.lines_verified)} líneas verificadas · {int(summary.counts.edges)} conexiones ·{" "}
          {int(summary.counts.coes_validated_edges)} validadas por COES
        </div>
        <div className="map-statusbar__right mono">
          <span>WGS84</span>
          <span>z {zoom.toFixed(1)}</span>
          <span>{dateLabel(summary.generated_at_utc)}</span>
        </div>
      </div>

      <div className="map-attribution-note">
        <Layers3 size={13} /> Geometrías OSINERGMIN · fondo Esri / OpenStreetMap
      </div>
    </div>
  );
}
