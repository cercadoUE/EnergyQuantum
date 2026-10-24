import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Subnet } from "../lib/types";
import { STATUS_LABELS, voltageColor, voltageMatchExpression } from "../lib/colors";
import { kv } from "../lib/format";

export interface LayerState {
  verifiedLines: boolean;
  unverifiedLines: boolean;
  stations: boolean;
  generation: boolean;
  labels: boolean;
}

export interface MapFocus {
  lon: number;
  lat: number;
  zoom?: number;
}

interface MapCanvasProps {
  mode?: "national" | "subnet";
  layers?: LayerState;
  voltages?: number[];
  departments?: string[];
  subnet?: Subnet | null;
  partition?: Record<string, number> | null;
  failedEdgeIds?: string[];
  focus?: MapFocus | null;
  resetKey?: number;
  fitPadding?: { top: number; right: number; bottom: number; left: number };
  onStationSelect?: (station: Record<string, any>) => void;
  onLineSelect?: (line: Record<string, any>) => void;
  onCursor?: (coords: { lon: number; lat: number } | null) => void;
  onZoom?: (zoom: number) => void;
  className?: string;
}

const PERU_BOUNDS: [[number, number], [number, number]] = [
  [-81.5, -18.6],
  [-68.3, -0.2],
];

const DATA = `${import.meta.env.BASE_URL}data`;
const geoCache = new Map<string, Promise<any>>();

function loadGeo(path: string): Promise<any> {
  if (!geoCache.has(path)) {
    geoCache.set(
      path,
      fetch(`${DATA}/${path}`).then((response) => {
        if (!response.ok) throw new Error(`No se pudo cargar ${path}`);
        return response.json();
      }),
    );
  }
  return geoCache.get(path)!;
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function popupHtml(title: string, rows: [string, string][], tone = "#22d3ee"): string {
  return `
    <div class="qg-popup">
      <div class="qg-popup__eyebrow" style="color:${tone}">SEIN · OSINERGMIN</div>
      <div class="qg-popup__title">${escapeHtml(title)}</div>
      <div class="qg-popup__rows">
        ${rows
          .map(
            ([label, value]) =>
              `<div class="qg-popup__row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`,
          )
          .join("")}
      </div>
    </div>`;
}

function filterExpression(voltages: number[], departments: string[], property = "kv") {
  const filters: any[] = [];
  if (voltages.length) filters.push(["in", ["get", property], ["literal", voltages]]);
  if (departments.length) {
    filters.push([
      "any",
      ...departments.map((department) => ["in", department, ["get", "departments"]]),
    ]);
  }
  if (!filters.length) return null;
  return filters.length === 1 ? filters[0] : ["all", ...filters];
}

function stationFilter(voltages: number[], departments: string[]) {
  const filters: any[] = [];
  if (voltages.length) filters.push(["in", ["get", "kv"], ["literal", voltages]]);
  if (departments.length) filters.push(["in", ["get", "department"], ["literal", departments]]);
  if (!filters.length) return null;
  return filters.length === 1 ? filters[0] : ["all", ...filters];
}

function subnetGeoJson(subnet: Subnet | null | undefined, partition: Record<string, number> | null | undefined) {
  if (!subnet) return { type: "FeatureCollection", features: [] as any[] };
  const nodes = subnet.nodes.map((node) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [node.lon, node.lat] },
    properties: {
      id: node.id,
      name: node.name,
      kv: node.voltage_kv,
      department: node.department,
      degree: node.verified_degree ?? 0,
      group: partition?.[node.id] ?? -1,
    },
  }));
  const edges = subnet.edges.map((edge) => ({
    type: "Feature",
    geometry: edge.geometry,
    properties: {
      id: edge.id,
      name: edge.line_names?.[0] ?? `${edge.source_name} – ${edge.target_name}`,
      source_name: edge.source_name,
      target_name: edge.target_name,
      kv: edge.voltage_kv,
      length_km: edge.length_km,
      failed: edge.failed,
    },
  }));
  return { nodes: { type: "FeatureCollection", features: nodes }, edges: { type: "FeatureCollection", features: edges } };
}

export default function MapCanvas({
  mode = "national",
  layers = {
    verifiedLines: true,
    unverifiedLines: true,
    stations: true,
    generation: true,
    labels: true,
  },
  voltages = [],
  departments = [],
  subnet = null,
  partition = null,
  failedEdgeIds = [],
  focus = null,
  resetKey = 0,
  fitPadding = { top: 40, right: 40, bottom: 60, left: 40 },
  onStationSelect,
  onLineSelect,
  onCursor,
  onZoom,
  className = "",
}: MapCanvasProps) {
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const callbacks = useRef({ onStationSelect, onLineSelect, onCursor, onZoom });
  callbacks.current = { onStationSelect, onLineSelect, onCursor, onZoom };

  useEffect(() => {
    if (!container.current) return;
    let cancelled = false;

    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: {
          basemap: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            minzoom: 0,
            maxzoom: 16,
            attribution:
              '&copy; <a href="https://www.esri.com/">Esri</a>, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          },
          "basemap-labels": {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            minzoom: 0,
            maxzoom: 16,
          },
        },
        layers: [
          {
            id: "basemap",
            type: "raster",
            source: "basemap",
            paint: { "raster-opacity": 1 },
          },
          {
            id: "basemap-labels",
            type: "raster",
            source: "basemap-labels",
            paint: { "raster-opacity": 0.72 },
          },
        ],
      },
      center: [-75.2, -9.4],
      zoom: 5.05,
      minZoom: 3.2,
      maxZoom: 14,
      attributionControl: false,
      maxBounds: [
        [-95, -25],
        [-55, 8],
      ],
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(
      new maplibregl.AttributionControl({ compact: true, customAttribution: "OSINERGMIN · EnergyQuantum Perú" }),
      "bottom-left",
    );

    map.on("mousemove", (event) => {
      callbacks.current.onCursor?.({ lon: event.lngLat.lng, lat: event.lngLat.lat });
    });
    map.on("mouseout", () => callbacks.current.onCursor?.(null));
    map.on("zoomend", () => callbacks.current.onZoom?.(map.getZoom()));
    map.on("error", (event) => {
      if (!cancelled && !map.isStyleLoaded()) {
        setError("No se pudo cargar el mapa base. Verifique la conexión a Internet.");
      }
      console.warn("MapLibre", event.error);
    });

    map.on("load", async () => {
      try {
        const [lines, stations, generation] = await Promise.all([
          loadGeo("map/lines.geojson"),
          loadGeo("map/stations.geojson"),
          loadGeo("map/generation.geojson"),
        ]);
        if (cancelled || !mapRef.current) return;

        map.addSource("lines", { type: "geojson", data: lines });
        map.addSource("stations", { type: "geojson", data: stations });
        map.addSource("generation", { type: "geojson", data: generation });
        map.addSource("subnet-edges", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addSource("subnet-nodes", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
        map.addSource("failed-edges", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });

        map.addLayer({
          id: "lines-halo",
          type: "line",
          source: "lines",
          filter: ["==", ["get", "verified"], true],
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": "#ffffff",
            "line-width": ["interpolate", ["linear"], ["zoom"], 4, 2.6, 8, 5.5, 12, 9],
            "line-opacity": 0.32,
            "line-blur": 2,
          },
        });
        map.addLayer({
          id: "lines-unverified",
          type: "line",
          source: "lines",
          filter: ["==", ["get", "verified"], false],
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": "#94a3b8",
            "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.8, 9, 1.8],
            "line-opacity": 0.55,
            "line-dasharray": [2, 2],
          },
        });
        map.addLayer({
          id: "lines-verified",
          type: "line",
          source: "lines",
          filter: ["==", ["get", "verified"], true],
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": voltageMatchExpression("kv") as any,
            "line-width": ["interpolate", ["linear"], ["zoom"], 4, 1.1, 8, 2.5, 12, 4.5],
            "line-opacity": 0.9,
          },
        });
        map.addLayer({
          id: "stations-isolated",
          type: "circle",
          source: "stations",
          filter: ["==", ["get", "in_graph"], false],
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 2, 10, 4],
            "circle-color": "#94a3b8",
            "circle-opacity": 0.55,
            "circle-stroke-width": 0.6,
            "circle-stroke-color": "#ffffff",
          },
        });
        map.addLayer({
          id: "stations",
          type: "circle",
          source: "stations",
          filter: ["==", ["get", "in_graph"], true],
          paint: {
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["get", "kv"],
              33,
              2.4,
              60,
              3.1,
              138,
              4.1,
              220,
              4.9,
              500,
              6.2,
            ],
            "circle-color": voltageMatchExpression("kv") as any,
            "circle-opacity": 0.96,
            "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 4, 0.8, 10, 1.6],
            "circle-stroke-color": "#ffffff",
          },
        });
        map.addLayer({
          id: "generation",
          type: "circle",
          source: "generation",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 2.2, 10, 3.6],
            "circle-color": "#10b981",
            "circle-opacity": 0.78,
            "circle-stroke-width": 0.8,
            "circle-stroke-color": "#064e3b",
          },
        });
        map.addLayer({
          id: "station-labels",
          type: "symbol",
          source: "stations",
          filter: ["all", ["==", ["get", "in_graph"], true], [">=", ["get", "kv"], 220]],
          layout: {
            "text-field": ["get", "name"],
            "text-font": ["Open Sans Semibold"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 5, 8, 9, 11],
            "text-offset": [0, 1.25],
            "text-anchor": "top",
            "text-allow-overlap": false,
            "text-ignore-placement": false,
            "text-padding": 2,
          },
          paint: {
            "text-color": "#0f172a",
            "text-halo-color": "rgba(255,255,255,0.92)",
            "text-halo-width": 1.4,
          },
        });

        map.addLayer({
          id: "subnet-halo",
          type: "line",
          source: "subnet-edges",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": "#22d3ee",
            "line-width": 9,
            "line-opacity": 0.28,
            "line-blur": 4,
          },
        });
        map.addLayer({
          id: "subnet-edges",
          type: "line",
          source: "subnet-edges",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": ["case", ["get", "failed"], "#fb7185", "#0891b2"],
            "line-width": ["interpolate", ["linear"], ["zoom"], 5, 2.2, 10, 4.8],
            "line-opacity": 0.98,
          },
        });
        map.addLayer({
          id: "failed-edges",
          type: "line",
          source: "failed-edges",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": "#f43f5e",
            "line-width": 5.5,
            "line-opacity": 0.95,
            "line-dasharray": [1.4, 1.1],
          },
        });
        map.addLayer({
          id: "subnet-nodes",
          type: "circle",
          source: "subnet-nodes",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 6, 10, 10],
            "circle-color": [
              "case",
              ["==", ["get", "group"], 0],
              "#0ea5e9",
              ["==", ["get", "group"], 1],
              "#f97316",
              "#0f766e",
            ],
            "circle-opacity": 1,
            "circle-stroke-width": 2.5,
            "circle-stroke-color": "#ffffff",
          },
        });
        map.addLayer({
          id: "subnet-labels",
          type: "symbol",
          source: "subnet-nodes",
          layout: {
            "text-field": ["get", "name"],
            "text-font": ["Open Sans Semibold"],
            "text-size": 11,
            "text-offset": [0, 1.5],
            "text-anchor": "top",
            "text-allow-overlap": true,
          },
          paint: {
            "text-color": "#0f172a",
            "text-halo-color": "rgba(255,255,255,0.95)",
            "text-halo-width": 1.6,
          },
        });

        const stationPopup = (feature: any) => {
          const props = feature.properties ?? {};
          return popupHtml(props.name, [
            ["Tensión", kv(props.kv)],
            ["Departamento", props.department ?? "—"],
            ["Empresa", props.company ?? "—"],
            ["Grado verificado", String(props.degree ?? 0)],
            ["En grafo", props.in_graph ? "Sí" : "No"],
          ], voltageColor(props.kv));
        };
        const linePopup = (feature: any) => {
          const props = feature.properties ?? {};
          return popupHtml(props.name ?? "Línea", [
            ["Tensión", kv(props.kv)],
            ["Estado", STATUS_LABELS[props.status] ?? props.status ?? "—"],
            ["Desde", props.from_name ?? "—"],
            ["Hasta", props.to_name ?? "—"],
            ["Longitud", `${Number(props.length_km ?? 0).toFixed(2)} km`],
          ], props.verified ? "#0891b2" : "#94a3b8");
        };

        for (const layer of ["stations", "stations-isolated"]) {
          map.on("mouseenter", layer, () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", layer, () => {
            map.getCanvas().style.cursor = "";
          });
          map.on("click", layer, (event) => {
            const feature = event.features?.[0];
            if (!feature) return;
            popupRef.current?.remove();
            popupRef.current = new maplibregl.Popup({ offset: 12, closeButton: true, maxWidth: "300px" })
              .setLngLat((feature.geometry as any).coordinates)
              .setHTML(stationPopup(feature))
              .addTo(map);
            callbacks.current.onStationSelect?.(feature.properties ?? {});
          });
        }

        for (const layer of ["lines-verified", "lines-unverified"]) {
          map.on("mouseenter", layer, () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", layer, () => {
            map.getCanvas().style.cursor = "";
          });
          map.on("click", layer, (event) => {
            const feature = event.features?.[0];
            if (!feature) return;
            popupRef.current?.remove();
            popupRef.current = new maplibregl.Popup({ offset: 10, closeButton: true, maxWidth: "320px" })
              .setLngLat(event.lngLat)
              .setHTML(linePopup(feature))
              .addTo(map);
            callbacks.current.onLineSelect?.(feature.properties ?? {});
          });
        }

        map.on("click", "subnet-edges", (event) => {
          const feature = event.features?.[0];
          if (!feature) return;
          const props = feature.properties ?? {};
          popupRef.current?.remove();
          popupRef.current = new maplibregl.Popup({ offset: 10, closeButton: true, maxWidth: "320px" })
            .setLngLat(event.lngLat)
            .setHTML(
              popupHtml(props.name ?? "Conexión verificada", [
                ["Tensión", kv(props.kv)],
                ["Longitud", `${Number(props.length_km ?? 0).toFixed(2)} km`],
                ["Desde", props.source_name ?? "—"],
                ["Hasta", props.target_name ?? "—"],
                ["Estado", props.failed ? "Falla simulada" : "Activa"],
              ], props.failed ? "#f43f5e" : "#0891b2"),
            )
            .addTo(map);
        });

        if (mode === "national") {
          map.fitBounds(PERU_BOUNDS, { padding: fitPadding, duration: 0 });
        }
        setReady(true);
      } catch (err) {
        console.error(err);
        setError("No se pudieron cargar los datos del mapa.");
      }
    });

    return () => {
      cancelled = true;
      popupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Filtros y visibilidad de capas.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const visibility = (id: string, visible: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    };
    visibility("lines-verified", layers.verifiedLines);
    visibility("lines-halo", layers.verifiedLines);
    visibility("lines-unverified", layers.unverifiedLines);
    visibility("stations", layers.stations);
    visibility("stations-isolated", layers.stations);
    visibility("generation", layers.generation);
    visibility("station-labels", layers.labels);

    const lineFilter = filterExpression(voltages, departments);
    for (const id of ["lines-verified", "lines-halo", "lines-unverified"]) {
      if (!map.getLayer(id)) continue;
      const base = id === "lines-unverified" ? ["==", ["get", "verified"], false] : ["==", ["get", "verified"], true];
      map.setFilter(id, (lineFilter ? ["all", base, lineFilter] : base) as any);
    }
    const stationsFilter = stationFilter(voltages, departments);
    for (const id of ["stations", "stations-isolated", "station-labels"]) {
      if (!map.getLayer(id)) continue;
      const base = id === "stations-isolated" ? ["==", ["get", "in_graph"], false] : ["==", ["get", "in_graph"], true];
      const extra = id === "station-labels" ? [">=", ["get", "kv"], 220] : true;
      const filter = stationsFilter
        ? ["all", base, ...(id === "station-labels" ? [extra as any] : []), stationsFilter]
        : ["all", base, ...(id === "station-labels" ? [extra as any] : [])];
      map.setFilter(id, filter as any);
    }
  }, [ready, layers, voltages, departments]);

  // Subred seleccionada y partición.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = map.getSource("subnet-edges") as maplibregl.GeoJSONSource | undefined;
    const nodeSource = map.getSource("subnet-nodes") as maplibregl.GeoJSONSource | undefined;
    if (!source || !nodeSource) return;
    const payload = subnetGeoJson(subnet, partition);
    source.setData(payload.edges as any);
    nodeSource.setData(payload.nodes as any);
    if (subnet?.nodes?.length) {
      const lons = subnet.nodes.map((node) => node.lon);
      const lats = subnet.nodes.map((node) => node.lat);
      map.fitBounds(
        [
          [Math.min(...lons), Math.min(...lats)],
          [Math.max(...lons), Math.max(...lats)],
        ],
        { padding: { top: 80, right: 80, bottom: 80, left: 80 }, maxZoom: 11, duration: 900 },
      );
    }
  }, [ready, subnet, partition]);

  // Fallas resaltadas.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = map.getSource("failed-edges") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    const failed = (subnet?.edges ?? []).filter((edge) => failedEdgeIds.includes(edge.id));
    source.setData({
      type: "FeatureCollection",
      features: failed.map((edge) => ({
        type: "Feature",
        geometry: edge.geometry,
        properties: { id: edge.id, name: edge.line_names?.[0] ?? "" },
      })),
    } as any);
  }, [ready, subnet, failedEdgeIds]);

  // Enfoque a estación / reinicio nacional.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (focus) {
      map.flyTo({ center: [focus.lon, focus.lat], zoom: focus.zoom ?? 10, duration: 900, essential: true });
    }
  }, [ready, focus]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || resetKey === 0) return;
    map.fitBounds(PERU_BOUNDS, { padding: fitPadding, duration: 900 });
  }, [ready, resetKey]);

  return (
    <div className={`map-canvas ${className}`}>
      <div ref={container} className="map-canvas__container" />
      {!ready && !error && (
        <div className="map-canvas__loading">
          <span className="spinner" />
          <span>Cargando infraestructura del SEIN…</span>
        </div>
      )}
      {error && <div className="map-canvas__error">{error}</div>}
    </div>
  );
}
