import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  Boxes,
  ChevronLeft,
  ChevronRight,
  Database,
  FlaskConical,
  GitCompareArrows,
  LayoutDashboard,
  Map,
  Menu,
  Network,
  Search,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { api } from "../lib/api";
import type { Station } from "../lib/types";
import { kv } from "../lib/format";
import { Badge } from "./ui";

const NAV = [
  {
    group: "Visión",
    items: [
      { to: "/mapa", label: "Mapa nacional", icon: Map },
      { to: "/red", label: "Explorador de red", icon: Network },
    ],
  },
  {
    group: "Análisis",
    items: [
      { to: "/subredes", label: "Subredes verificadas", icon: Boxes },
      { to: "/optimizacion", label: "Optimización", icon: Sparkles },
      { to: "/fallas", label: "Simulador de fallas", icon: Zap },
    ],
  },
  {
    group: "Laboratorio",
    items: [
      { to: "/comparacion", label: "Comparación", icon: GitCompareArrows },
      { to: "/sintetico", label: "Red sintética", icon: FlaskConical },
    ],
  },
  {
    group: "Datos",
    items: [{ to: "/fuentes", label: "Fuentes y metodología", icon: Database }],
  },
];

const PAGE_META: Record<string, { title: string; subtitle: string; icon: any }> = {
  "/mapa": {
    title: "Mapa eléctrico del Perú",
    subtitle: "Infraestructura del SEIN sobre geometrías oficiales de OSINERGMIN.",
    icon: Map,
  },
  "/red": {
    title: "Explorador de red",
    subtitle: "Subestaciones, líneas y componentes verificadas del snapshot nacional.",
    icon: Network,
  },
  "/subredes": {
    title: "Subredes verificadas",
    subtitle: "Seleccione una componente conectada y construya una instancia de 2 a 12 nodos.",
    icon: Boxes,
  },
  "/optimizacion": {
    title: "Optimización de la red real",
    subtitle: "Partición binaria con solucionadores exactos, heurísticos y QAOA.",
    icon: Sparkles,
  },
  "/fallas": {
    title: "Simulador de fallas",
    subtitle: "Escenarios topológicos antes/después sin inventar suministro eléctrico.",
    icon: Zap,
  },
  "/comparacion": {
    title: "Comparación de resultados",
    subtitle: "Brecha, tiempos y calidad de la partición entre métodos.",
    icon: GitCompareArrows,
  },
  "/sintetico": {
    title: "Laboratorio sintético",
    subtitle: "Red de 12 nodos con supuestos explícitos, separada de la capa real.",
    icon: FlaskConical,
  },
  "/fuentes": {
    title: "Fuentes y metodología",
    subtitle: "Procedencia, reglas de validación y límites científicos del prototipo.",
    icon: Database,
  },
};

function GlobalSearch({ compact = false }: { compact?: boolean }) {
  const [stations, setStations] = useState<Station[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api
      .stations()
      .then((payload) => setStations(payload.stations))
      .catch(() => setStations([]));
  }, []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const results = useMemo(() => {
    const term = query.trim().toUpperCase();
    if (!term) return [];
    return stations
      .filter(
        (station) =>
          station.name?.toUpperCase().includes(term) ||
          station.department?.toUpperCase().includes(term),
      )
      .slice(0, 8);
  }, [query, stations]);

  return (
    <div className={`global-search ${compact ? "global-search--compact" : ""}`} ref={containerRef}>
      <Search size={16} />
      <input
        ref={inputRef}
        value={query}
        placeholder="Buscar subestación o departamento…"
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && results[0]) {
            navigate(`/mapa?station=${results[0].id}`);
            setOpen(false);
            setQuery("");
          }
        }}
      />
      <kbd>Ctrl K</kbd>
      {open && query.trim() && (
        <div className="global-search__results">
          {results.length === 0 && <div className="global-search__empty">Sin coincidencias</div>}
          {results.map((station) => (
            <button
              type="button"
              key={station.id}
              className="global-search__item"
              onClick={() => {
                navigate(`/mapa?station=${station.id}`);
                setOpen(false);
                setQuery("");
              }}
            >
              <span className="global-search__dot" style={{ background: "#0891b2" }} />
              <span>
                <strong>{station.name}</strong>
                <small>
                  {station.department ?? "Sin departamento"} · {kv(station.voltage_kv)}
                </small>
              </span>
              <span className="global-search__degree">{station.degree ?? 0} conex.</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AppShell() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const meta = PAGE_META[location.pathname] ?? PAGE_META["/mapa"];
  const PageIcon = meta.icon;

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  return (
    <div className={`app-shell ${collapsed ? "app-shell--collapsed" : ""}`}>
      <aside className={`sidebar ${mobileOpen ? "is-open" : ""}`}>
        <div className="sidebar__brand">
          <div className="brand-mark">
            <span className="brand-mark__ring" />
            <Zap size={18} />
          </div>
          <div className="brand-copy">
            <strong>EnergyQuantum</strong>
            <span>PERÚ / LABORATORIO</span>
          </div>
          <button
            type="button"
            className="icon-button sidebar__collapse"
            onClick={() => setCollapsed((value) => !value)}
            aria-label="Colapsar barra lateral"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        <nav className="sidebar__nav">
          {NAV.map((group) => (
            <div className="nav-group" key={group.group}>
              <div className="nav-group__label">{group.group}</div>
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => `nav-item ${isActive ? "is-active" : ""}`}
                    title={collapsed ? item.label : undefined}
                  >
                    <span className="nav-item__icon">
                      <Icon size={18} />
                    </span>
                    <span className="nav-item__label">{item.label}</span>
                    {item.to === "/subredes" && <span className="nav-item__badge">48</span>}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="source-pill">
            <span className="status-dot" />
            <div>
              <strong>OSINERGMIN</strong>
              <small>Snapshot oficial · 17 capas</small>
            </div>
          </div>
          <div className="sidebar__note">
            <Activity size={14} />
            <span>Modo académico. Sin instrucciones de operación eléctrica.</span>
          </div>
        </div>
      </aside>

      {mobileOpen && <div className="sidebar-backdrop" onClick={() => setMobileOpen(false)} />}

      <div className="main-shell">
        <header className="topbar">
          <button type="button" className="icon-button topbar__menu" onClick={() => setMobileOpen(true)}>
            <Menu size={18} />
          </button>
          <div className="topbar__title">
            <div className="topbar__icon">
              <PageIcon size={17} />
            </div>
            <div>
              <h1>{meta.title}</h1>
              <p>{meta.subtitle}</p>
            </div>
          </div>
          <div className="topbar__actions">
            <GlobalSearch compact />
            <Badge tone="green" dot>
              API local
            </Badge>
            <a className="button button--ghost button--sm" href="/data/manifest.json" target="_blank" rel="noreferrer">
              <Database size={14} /> Manifest
            </a>
          </div>
        </header>

        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
