"""Construcción del grafo eléctrico a partir de extremos explícitos.

Regla central: una línea solo se convierte en arista si sus atributos
NODO_SALIDA y NODO_LLEGADA identifican de forma inequívoca dos estaciones.
La proximidad geométrica se usa únicamente para desempatar candidatos del mismo
nombre; nunca para crear una conexión por cruce o cercanía.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
import json
from pathlib import Path
from typing import Any, Iterable

import networkx as nx

from ..geospatial.geometry import (
    geometry_length_km,
    haversine_km,
    name_variants,
    normalize_text,
    parse_number,
    validate_geometry,
)
from ..geospatial.processing import PROCESSED_DIR, load_processed
from ..models.graph_model import ROOT

NETWORK_DIR = ROOT / "data" / "processed"
MAX_ENDPOINT_DISTANCE_KM = 12.0
VOLTAGE_TOLERANCE = 0.6


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _edge_id(a: str, b: str) -> str:
    pair = "|".join(sorted((a, b)))
    return "ed_" + sha1(pair.encode("utf-8")).hexdigest()[:12]


@dataclass
class EndpointResolution:
    node_id: str | None
    method: str
    status: str
    candidates: list[str] = field(default_factory=list)
    distance_km: float | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "method": self.method,
            "status": self.status,
            "candidate_count": len(self.candidates),
            "distance_km": None if self.distance_km is None else round(self.distance_km, 3),
            "note": self.note,
        }


def _station_voltages(station: dict[str, Any]) -> list[float]:
    values = station.get("voltages_kv") or []
    if not values and station.get("voltage_kv") is not None:
        values = [station["voltage_kv"]]
    return [float(v) for v in values if v is not None]


def _voltage_rank(station: dict[str, Any], voltage: float | None) -> float:
    if voltage is None:
        return 0.0
    values = _station_voltages(station)
    if not values:
        return 1.0
    if any(abs(value - voltage) <= VOLTAGE_TOLERANCE for value in values):
        return 0.0
    return 2.0 + min(abs(value - voltage) for value in values) / 100.0


def resolve_endpoint(
    name: str | None,
    voltage: float | None,
    endpoint: tuple[float, float] | None,
    index: dict[str, list[str]],
    stations: dict[str, dict[str, Any]],
) -> EndpointResolution:
    if not name:
        return EndpointResolution(None, "none", "missing", note="NODO_SALIDA/LLEGADA vacío.")
    variants = name_variants(name)
    candidates: list[str] = []
    for variant in variants:
        for node_id in index.get(variant, []):
            if node_id not in candidates:
                candidates.append(node_id)
    if not candidates:
        return EndpointResolution(None, "explicit_name", "not_found", note=f"Sin estación para '{name}'.")

    ranked: list[tuple[float, float, str]] = []
    for node_id in candidates:
        station = stations[node_id]
        vrank = _voltage_rank(station, voltage)
        distance = (
            haversine_km(endpoint, (station["lon"], station["lat"]))
            if endpoint is not None
            else 0.0
        )
        ranked.append((vrank, distance, node_id))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))

    best_vrank = ranked[0][0]
    voltage_pool = [item for item in ranked if item[0] == best_vrank]
    # Si no hay coincidencia exacta de tensión, un candidato sin tensión conocida
    # es preferible a uno con tensión claramente distinta.
    if best_vrank >= 2.0:
        neutral = [item for item in ranked if item[0] == 1.0]
        if neutral:
            voltage_pool = neutral
    nearest = min(item[1] for item in voltage_pool)
    close = [item for item in voltage_pool if item[1] <= nearest + 0.5]
    if nearest > MAX_ENDPOINT_DISTANCE_KM:
        return EndpointResolution(
            None,
            "explicit_name",
            "far_from_geometry",
            [item[2] for item in voltage_pool],
            nearest,
            f"El nombre existe pero el extremo está a {nearest:.1f} km de la estación.",
        )
    if len(close) == 1:
        node_id = close[0][2]
        method = "explicit_name"
        if len(candidates) > 1:
            method += "+voltage" if best_vrank == 0 else "+distance"
            method += "+proximity"
        return EndpointResolution(
            node_id,
            method,
            "resolved",
            [item[2] for item in voltage_pool],
            nearest,
            None,
        )
    return EndpointResolution(
        None,
        "explicit_name",
        "ambiguous",
        [item[2] for item in close],
        nearest,
        "Varios nodos del mismo nombre/tensión a distancia comparable.",
    )


def _line_available(line: dict[str, Any]) -> bool:
    state = (line.get("state") or "").strip().upper()
    return state in {"", "ES", "EN SERVICIO", "OPERATIVO"}


def _line_geometry_ok(line: dict[str, Any]) -> bool:
    geometry = line.get("geometry")
    if not geometry:
        return False
    errors = validate_geometry(geometry)
    return not errors


def build_network(
    processed: dict[str, Any] | None = None,
    *,
    source_metadata: dict[str, Any] | None = None,
    include_isolated: bool = True,
) -> dict[str, Any]:
    processed = processed or load_processed()
    station_list = list(processed.get("stations", []))
    line_list = list(processed.get("lines", []))
    generation_list = list(processed.get("generation", []))
    if not station_list:
        raise ValueError("No hay estaciones procesadas.")

    stations = {station["id"]: station for station in station_list}
    index: dict[str, list[str]] = defaultdict(list)
    for station in station_list:
        keys = set(name_variants(station.get("name")))
        for alias in station.get("aliases", []) or []:
            keys |= name_variants(alias)
        for key in keys:
            if station["id"] not in index[key]:
                index[key].append(station["id"])

    nodes: dict[str, dict[str, Any]] = {}
    for station in station_list:
        nodes[station["id"]] = {
            **station,
            "node_type": "substation",
            "in_verified_graph": False,
            "verified_degree": 0,
            "source": "OSINERGMIN",
            "provenance": "OFICIAL",
            "identity_provenance": "DERIVADO",
            "validation": "valid",
        }

    lines: list[dict[str, Any]] = []
    verified_lines: list[dict[str, Any]] = []
    for original in line_list:
        line = dict(original)
        line.setdefault("source_ids", [line.get("source_id")])
        errors = list(line.get("geometry_errors") or [])
        if not _line_geometry_ok(line):
            line["connectivity_status"] = "invalid_geometry"
            line["resolution"] = {
                "from": EndpointResolution(None, "none", "invalid_geometry").to_dict(),
                "to": EndpointResolution(None, "none", "invalid_geometry").to_dict(),
            }
            lines.append(line)
            continue

        from_coord, to_coord = _endpoints(line.get("geometry"))
        from_res = resolve_endpoint(line.get("from_name"), parse_number(line.get("voltage_kv")), from_coord, index, stations)
        to_res = resolve_endpoint(line.get("to_name"), parse_number(line.get("voltage_kv")), to_coord, index, stations)
        line["resolution"] = {"from": from_res.to_dict(), "to": to_res.to_dict()}
        line["endpoint_from"] = from_res.node_id
        line["endpoint_to"] = to_res.node_id

        if from_res.status != "resolved" or to_res.status != "resolved":
            status = "unverified_" + (
                from_res.status if from_res.status != "resolved" else to_res.status
            )
            line["connectivity_status"] = status
            line["optimization_ready"] = False
            lines.append(line)
            continue
        if from_res.node_id == to_res.node_id:
            line["connectivity_status"] = "invalid_self_loop"
            line["optimization_ready"] = False
            lines.append(line)
            continue

        line["connectivity_status"] = "verified"
        line["verification_method"] = "explicit_endpoint_attributes"
        line["coes_validated"] = False
        line["optimization_ready"] = _line_available(line)
        line["available"] = _line_available(line)
        line["failed"] = False
        line["length_km"] = float(line.get("length_km") or geometry_length_km(line.get("geometry")) or 0.0)
        if not line["length_km"] > 0:
            errors.append("Longitud no positiva.")
        for endpoint in (from_res, to_res):
            station = nodes[endpoint.node_id]
            station["in_verified_graph"] = True
            station["verified_degree"] += 1
        voltage = parse_number(line.get("voltage_kv"))
        if voltage is not None:
            for endpoint in (from_res, to_res):
                values = _station_voltages(nodes[endpoint.node_id])
                if values and not any(abs(value - voltage) <= VOLTAGE_TOLERANCE for value in values):
                    errors.append(
                        f"Tensión de línea {voltage:g} kV no figura en la estación {nodes[endpoint.node_id]['name']}."
                    )
        line["geometry_errors"] = errors
        verified_lines.append(line)
        lines.append(line)

    edges = _aggregate_edges(verified_lines, nodes)
    graph = _networkx_graph(nodes, edges, verified_only=True)
    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    component_of: dict[str, int] = {}
    for idx, component in enumerate(components):
        for node_id in component:
            component_of[node_id] = idx
            nodes[node_id]["component"] = idx
    for node_id in nodes:
        nodes[node_id].setdefault("component", None)

    quality = _quality_report(nodes, lines, edges, graph, components, processed)
    network = {
        "schema_version": 2,
        "generated_at_utc": utc_now(),
        "source": {
            "institution": "OSINERGMIN",
            "service": (
                "https://gisem.osinergmin.gob.pe/serverosih/rest/services/"
                "Electricidad/MapaSEIN_Operacion/MapServer"
            ),
            "source_metadata": {
                key: value
                for key, value in (source_metadata or {}).items()
                if key != "loaded_layers"
            },
            "provenance": {
                "geometry": "OFICIAL",
                "attributes": "OFICIAL",
                "node_identity": "DERIVADO",
                "edges": "DERIVADO",
                "weights": "DERIVADO",
                "coes_validation": "NO_AUTOMATIZADA",
                "demand": "NO_DISPONIBLE",
                "generation_dispatch": "NO_DISPONIBLE",
            },
        },
        "nodes": sorted(nodes.values(), key=lambda item: (item.get("department") or "", item["name"], item["id"])),
        "edges": sorted(edges, key=lambda item: (item["source"], item["target"])),
        "lines": sorted(lines, key=lambda item: item.get("source_id", "")),
        "generation": generation_list,
        "quality": quality,
        "metadata": {
            "rule": (
                "Una línea es arista solo si NODO_SALIDA y NODO_LLEGADA resuelven "
                "inequívocamente a dos estaciones. Proximidad solo desempata nombres."
            ),
            "verified_means": (
                "Coincidencia de atributos explícitos de extremos con estaciones OSINERGMIN; "
                "no constituye validación eléctrica ni confirmación de COES."
            ),
            "station_merge_radius_km": processed.get("report", {}).get("merge_radius_km", 0.75),
            "coes": "No se declara ninguna conexión validada por COES.",
            "generation": "Capacidad instalada/efectiva es un atributo; no se usa como despacho.",
            "demand": "OSINERGMIN no provee demanda por subestación en este servicio.",
        },
    }
    if not include_isolated:
        keep = {node["id"] for node in nodes.values() if node["in_verified_graph"]}
        network["nodes"] = [node for node in network["nodes"] if node["id"] in keep]
    return network


def _endpoints(geometry: dict[str, Any] | None) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    if not geometry:
        return None, None
    if geometry.get("type") == "LineString":
        coords = geometry.get("coordinates") or []
        if len(coords) >= 2:
            return (float(coords[0][0]), float(coords[0][1])), (
                float(coords[-1][0]),
                float(coords[-1][1]),
            )
    if geometry.get("type") == "MultiLineString":
        coords = geometry.get("coordinates") or []
        if coords and coords[0] and coords[-1]:
            return (float(coords[0][0][0]), float(coords[0][0][1])), (
                float(coords[-1][-1][0]),
                float(coords[-1][-1][1]),
            )
    return None, None


def _aggregate_edges(lines: list[dict[str, Any]], nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for line in lines:
        pair = tuple(sorted((line["endpoint_from"], line["endpoint_to"])))
        groups[pair].append(line)
    edges: list[dict[str, Any]] = []
    for (a, b), group in sorted(groups.items()):
        lengths = [float(line.get("length_km") or 0.0) for line in group]
        voltages = sorted({float(line["voltage_kv"]) for line in group if line.get("voltage_kv") is not None})
        geometries = []
        for line in group:
            geom = line.get("geometry")
            if not geom:
                continue
            if geom.get("type") == "LineString":
                geometries.append(geom.get("coordinates") or [])
            elif geom.get("type") == "MultiLineString":
                geometries.extend(geom.get("coordinates") or [])
        edges.append(
            {
                "id": _edge_id(a, b),
                "source": a,
                "target": b,
                "source_name": nodes[a]["name"],
                "target_name": nodes[b]["name"],
                "length_km": round(sum(lengths), 4),
                "length_source": "SUMA_LINEAS_VERIFICADAS",
                "voltage_kv": max(voltages) if voltages else None,
                "voltages_kv": voltages,
                "line_ids": [line["source_id"] for line in group],
                "line_names": [line["name"] for line in group],
                "line_count": len(group),
                "parallel": len(group) > 1,
                "available": all(bool(line.get("available", True)) for line in group),
                "failed": False,
                "state": sorted({str(line.get("state")) for line in group if line.get("state")}),
                "geometry": (
                    {"type": "MultiLineString", "coordinates": geometries}
                    if len(geometries) > 1
                    else {"type": "LineString", "coordinates": geometries[0]}
                    if geometries
                    else None
                ),
                "data_source": "OSINERGMIN",
                "provenance": "DERIVADO",
                "validation": "verified_endpoint_attributes",
                "coes_validated": False,
                "optimization_ready": True,
            }
        )
    return edges


def _networkx_graph(
    nodes: dict[str, dict[str, Any]],
    edges: Iterable[dict[str, Any]],
    *,
    verified_only: bool = True,
) -> nx.Graph:
    graph = nx.Graph()
    for node in nodes.values():
        graph.add_node(node["id"], **{k: v for k, v in node.items() if _scalar(v)})
    for edge in edges:
        if verified_only and edge.get("validation") != "verified_endpoint_attributes":
            continue
        graph.add_edge(
            edge["source"],
            edge["target"],
            weight=float(edge.get("length_km") or 0.0),
            **{k: v for k, v in edge.items() if _scalar(v)},
        )
    return graph


def _scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _quality_report(
    nodes: dict[str, dict[str, Any]],
    lines: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    graph: nx.Graph,
    components: list[set[str]],
    processed: dict[str, Any],
) -> dict[str, Any]:
    status = Counter(line.get("connectivity_status") for line in lines)
    unresolved = [
        {
            "source_id": line.get("source_id"),
            "name": line.get("name"),
            "from": line.get("from_name"),
            "to": line.get("to_name"),
            "voltage_kv": line.get("voltage_kv"),
            "status": line.get("connectivity_status"),
            "resolution": line.get("resolution"),
        }
        for line in lines
        if line.get("connectivity_status") != "verified"
    ]
    length_warnings = [
        {"source_id": line["source_id"], "name": line.get("name"), "warnings": line.get("geometry_errors")}
        for line in lines
        if line.get("geometry_errors")
    ]
    isolated = [node["id"] for node in nodes.values() if not node["in_verified_graph"]]
    bridges = []
    if graph.number_of_edges():
        bridges = [list(edge) for edge in nx.bridges(graph)]
    bipartite_cycles = 0
    try:
        bipartite_cycles = len(nx.cycle_basis(graph))
    except nx.NetworkXException:
        bipartite_cycles = 0
    return {
        "generated_at_utc": utc_now(),
        "nodes_total": len(nodes),
        "nodes_in_verified_graph": sum(1 for node in nodes.values() if node["in_verified_graph"]),
        "nodes_isolated": len(isolated),
        "isolated_node_ids": isolated,
        "edges_verified": len(edges),
        "lines_total": len(lines),
        "lines_verified": status.get("verified", 0),
        "lines_unverified": len(lines) - status.get("verified", 0),
        "line_status": dict(status),
        "unverified_lines": unresolved,
        "duplicate_station_groups": sum(
            1 for node in nodes.values() if node.get("identity_status") == "merged_duplicate"
        ),
        "duplicate_stations_merged": processed.get("report", {}).get("station_duplicates_merged", 0),
        "duplicate_lines_removed": processed.get("report", {}).get("line_duplicates_removed", []),
        "components_verified": len(components),
        "components_with_edges": sum(1 for c in components if any(graph.degree(n) for n in c)),
        "largest_component_nodes": max((len(c) for c in components), default=0),
        "largest_component_edges": graph.subgraph(components[0]).number_of_edges() if components else 0,
        "bridges": bridges,
        "cycle_basis_size": bipartite_cycles,
        "geometry_warnings": length_warnings,
        "checks": {
            "duplicate_node_ids": len(nodes) - len({node["id"] for node in nodes.values()}),
            "duplicate_edge_pairs": len(edges) - len({tuple(sorted((e["source"], e["target"]))) for e in edges}),
            "self_loops": sum(1 for e in edges if e["source"] == e["target"]),
            "invalid_geometries": status.get("invalid_geometry", 0),
            "unverified_missing_endpoints": sum(
                1 for line in lines if line.get("connectivity_status", "").startswith("unverified_missing")
            ),
            "coes_validated_edges": 0,
        },
        "notes": [
            "Una conexión verificada significa extremos explícitos coincidentes, no validación COES.",
            "Los ciclos no son necesariamente errores; se reportan como estructura.",
            "Las componentes aisladas no implican falta de suministro; no hay demanda ni flujo.",
        ],
    }


def save_network(network: dict[str, Any], out_dir: str | Path = NETWORK_DIR) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "sein_network.json"
    path.write_text(
        json.dumps(network, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    quality = out_dir / "sein_topology_report.json"
    quality.write_text(json.dumps(network["quality"], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_network_snapshot(out_dir: str | Path = NETWORK_DIR) -> dict[str, Any]:
    out_dir = Path(out_dir)
    path = out_dir / "sein_network.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Ejecute: python -m scripts.download_sein && "
            "python -m scripts.build_network"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def subnet_graph(network: dict[str, Any], *, available_only: bool = True) -> nx.Graph:
    """Grafo de nodos/aristas verificadas para exploración y optimización."""
    nodes = {node["id"]: node for node in network.get("nodes", [])}
    graph = nx.Graph()
    for node in nodes.values():
        graph.add_node(node["id"], **node)
    for edge in network.get("edges", []):
        if edge.get("validation") != "verified_endpoint_attributes":
            continue
        if available_only and (edge.get("failed") or not edge.get("available", True)):
            continue
        graph.add_edge(edge["source"], edge["target"], **edge)
    return graph
