import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Database,
  ExternalLink,
  FileJson,
  GitBranch,
  Globe2,
  Info,
  Layers3,
  LockKeyhole,
  ShieldCheck,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import { Badge, ErrorState, Panel, SectionTitle, Spinner, StatCard } from "../components/ui";
import { api } from "../lib/api";
import type { NetworkSummary, SourceInfo, Tone } from "../lib/types";
import { dateTimeLabel, int, km } from "../lib/format";

const FALLBACK_LABELS: SourceInfo["labels"] = [
  { name: "OFICIAL", tone: "cyan", description: "Geometrías y atributos descargados de OSINERGMIN." },
  { name: "DERIVADO", tone: "blue", description: "Identidad de estaciones, resolución de extremos, aristas y pesos." },
  { name: "VALIDADO", tone: "green", description: "Solo con evidencia explícita. COES no se automatizó." },
  { name: "SIMULADO", tone: "amber", description: "Demanda, generación fijada en 0, pesos y fallas de escenario." },
];

const FALLBACK_PIPELINE = [
  "ArcGIS REST · MapServer OSINERGMIN",
  "GeoJSON crudo con caché y SHA-256",
  "Normalización de estaciones y líneas",
  "Resolución de extremos explícitos",
  "Grafo verificado y componentes",
  "Subred conectada de 2 a 12 nodos",
  "Instancia y solucionadores clásicos/QAOA",
];

const FALLBACK_LIMITATIONS = [
  "No se modelan flujo AC/DC, frecuencia, protecciones, estabilidad ni energía no suministrada.",
  "La demanda por subestación no está disponible en la fuente; se usa un supuesto SIMULADO.",
  "La generación se fija en 0 porque no hay despacho por subestación.",
  "Las fallas son escenarios topológicos, no órdenes de operación.",
  "Los resultados no demuestran ventaja cuántica ni reducción de riesgo climático.",
];

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceInfo | null>(null);
  const [summary, setSummary] = useState<NetworkSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.summary().then(setSummary).catch(() => undefined);
    api
      .sources()
      .then(setSources)
      .catch(() => {
        setSources({
          source: {
            institution: "OSINERGMIN",
            service:
              "https://gisem.osinergmin.gob.pe/serverosih/rest/services/Electricidad/MapaSEIN_Operacion/MapServer",
            provenance: "OFICIAL",
            layers: [],
          },
          quality: {},
          processing: {},
          labels: FALLBACK_LABELS,
          pipeline: FALLBACK_PIPELINE,
          validation: {
            rule: "Una línea es arista solo si NODO_SALIDA y NODO_LLEGADA resuelven a dos estaciones.",
            proximity: "La proximidad solo desempata candidatos con el mismo nombre; no crea conexiones.",
            coes: "NO_AUTOMATIZADA · ninguna arista se declara validada por COES.",
            supply: "Una componente conectada no certifica suministro eléctrico.",
          },
          limitations: FALLBACK_LIMITATIONS,
        });
      });
  }, []);

  useEffect(() => {
    if (sources && !error) return;
    if (!sources && !summary) {
      const timer = window.setTimeout(() => {
        if (!sources && !summary) setError("No se pudo cargar la información de fuentes.");
      }, 4000);
      return () => window.clearTimeout(timer);
    }
  }, [sources, summary, error]);

  if (error) {
    return (
      <div className="page-pad">
        <ErrorState message={error} />
      </div>
    );
  }
  if (!sources || !summary) {
    return (
      <div className="page-pad loading-page">
        <Spinner label="Cargando procedencia y metodología…" />
      </div>
    );
  }

  return (
    <div className="page-pad sources-page">
      <section className="sources-hero">
        <div className="sources-hero__copy">
          <div className="eyebrow">Procedencia explícita</div>
          <h2>Datos oficiales. Decisiones derivadas. Escenarios simulados.</h2>
          <p>
            La plataforma separa lo que OSINERGMIN publica de lo que el proyecto calcula y de lo
            que es un supuesto. Ninguna arista se declara validada por COES.
          </p>
          <div className="quality-note">
            {sources.labels.map((label) => (
              <Badge key={label.name} tone={label.tone as Tone}>
                {label.name}
              </Badge>
            ))}
          </div>
        </div>
        <div className="sources-hero__stats">
          <StatCard label="Capas oficiales" value={int(sources.source.layers?.length ?? 17)} tone="cyan" icon={<Layers3 size={15} />} />
          <StatCard label="Estaciones" value={int(summary.counts.stations)} tone="blue" icon={<Database size={15} />} />
          <StatCard label="Líneas" value={int(summary.counts.lines)} tone="green" icon={<GitBranch size={15} />} />
          <StatCard label="COES" value="No autom." tone="rose" icon={<LockKeyhole size={15} />} />
        </div>
      </section>

      <div className="sources-grid">
        <Panel className="sources-main">
          <SectionTitle
            eyebrow="Fuente primaria"
            title="OSINERGMIN · Mapa del SEIN"
            description="Geometrías y atributos descargados del servicio ArcGIS REST. La UI no descarga datos en tiempo de ejecución."
            actions={
              <a
                className="button button--ghost button--sm"
                href={sources.source.service}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={14} /> Abrir servicio
              </a>
            }
          />
          <dl className="detail-list detail-list--wide">
            <div>
              <dt>Institución</dt>
              <dd>{sources.source.institution}</dd>
            </div>
            <div>
              <dt>Servicio</dt>
              <dd className="mono break">{sources.source.service}</dd>
            </div>
            <div>
              <dt>Descarga</dt>
              <dd>{dateTimeLabel(sources.source.downloaded_at_utc ?? summary.source.downloaded_at_utc)}</dd>
            </div>
            <div>
              <dt>Procedencia</dt>
              <dd><Badge tone="cyan">{sources.source.provenance ?? "OFICIAL"}</Badge></dd>
            </div>
          </dl>
          <div className="info-strip">
            <Info size={14} />
            <span>
              {sources.source.classification_note ??
                "OFICIAL identifica la descarga; el procesamiento posterior es DERIVADO."}
            </span>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Capa</th>
                  <th>Rol</th>
                  <th>Geometría</th>
                  <th>Tensión</th>
                </tr>
              </thead>
              <tbody>
                {(sources.source.layers ?? []).map((layer) => (
                  <tr key={`${layer.layer_id}-${layer.name}`}>
                    <td>{layer.name}</td>
                    <td>
                      <Badge tone={layer.role === "substation" ? "cyan" : layer.role === "line" ? "blue" : "green"}>
                        {layer.role}
                      </Badge>
                    </td>
                    <td className="mono">{layer.geometry_type}</td>
                    <td className="mono">{layer.voltage_kv ? `${layer.voltage_kv} kV` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="sources-side">
          <Panel>
            <div className="panel-heading">
              <div>
                <div className="eyebrow">Etiquetas</div>
                <h3>Qué significa cada dato</h3>
              </div>
              <ShieldCheck size={16} />
            </div>
            <div className="label-stack">
              {sources.labels.map((label) => (
                <div className={`label-card label-card--${label.tone}`} key={label.name}>
                  <strong>{label.name}</strong>
                  <p>{label.description}</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel>
            <div className="panel-heading">
              <div>
                <div className="eyebrow">Calidad</div>
                <h3>Snapshot procesado</h3>
              </div>
              <CheckCircle2 size={16} />
            </div>
            <div className="quality-grid">
              <div><small>Estaciones</small><strong>{int(summary.counts.stations)}</strong></div>
              <div><small>En grafo</small><strong>{int(summary.counts.stations_in_verified_graph)}</strong></div>
              <div><small>Líneas verificadas</small><strong>{int(summary.counts.lines_verified)}</strong></div>
              <div><small>No verificadas</small><strong>{int(summary.counts.lines_unverified)}</strong></div>
              <div><small>Componentes</small><strong>{int(summary.counts.components_with_edges)}</strong></div>
              <div><small>Mayor componente</small><strong>{int(summary.quality.largest_component_nodes)} nodos</strong></div>
            </div>
            <div className="info-strip info-strip--muted">
              <Globe2 size={14} />
              <span>
                {int(summary.counts.generation)} centrales de generación con capacidad instalada; no se
                usan como despacho.
              </span>
            </div>
          </Panel>
        </div>
      </div>

      <Panel>
        <SectionTitle
          eyebrow="Pipeline"
          title="De la fuente oficial a la instancia de optimización"
          description="Cada transformación conserva IDs, procedencia y motivos de rechazo."
        />
        <div className="pipeline">
          {sources.pipeline.map((step, index) => (
            <div className="pipeline__step" key={step}>
              <span className="pipeline__index">{String(index + 1).padStart(2, "0")}</span>
              <span>{step}</span>
              {index < sources.pipeline.length - 1 && <span className="pipeline__line" />}
            </div>
          ))}
        </div>
      </Panel>

      <div className="sources-grid sources-grid--two">
        <Panel>
          <SectionTitle
            eyebrow="Reglas"
            title="Qué se considera verificado"
            description="La proximidad nunca crea una conexión por sí sola."
          />
          <ul className="rule-list">
            <li>
              <CheckCircle2 size={16} />
              <span>{sources.validation.rule}</span>
            </li>
            <li>
              <CheckCircle2 size={16} />
              <span>{sources.validation.proximity}</span>
            </li>
            <li>
              <XCircle size={16} />
              <span>{sources.validation.coes}</span>
            </li>
            <li>
              <AlertTriangle size={16} />
              <span>{sources.validation.supply}</span>
            </li>
          </ul>
          <div className="quality-note">
            <Badge tone="cyan">0 aristas COES</Badge>
            <Badge tone="blue">618 líneas verificadas</Badge>
            <Badge tone="amber">359 no verificadas</Badge>
          </div>
        </Panel>

        <Panel>
          <SectionTitle
            eyebrow="Límites"
            title="Lo que este prototipo no demuestra"
            description="La honestidad científica es parte del producto."
          />
          <ul className="clean-list clean-list--warning">
            {sources.limitations.map((limitation) => (
              <li key={limitation}>
                <TriangleAlert size={14} /> {limitation}
              </li>
            ))}
          </ul>
          <div className="button-row">
            <a className="button button--ghost button--sm" href="/data/manifest.json" target="_blank" rel="noreferrer">
              <FileJson size={14} /> Manifest de datos
            </a>
            <a className="button button--ghost button--sm" href={sources.source.service} target="_blank" rel="noreferrer">
              <ArrowUpRight size={14} /> Fuente original
            </a>
          </div>
        </Panel>
      </div>
    </div>
  );
}
