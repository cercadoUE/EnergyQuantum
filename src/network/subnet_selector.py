"""Selección de subredes conectadas conservando IDs y procedencia."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import heapq
import json
from typing import Any, Iterable

import networkx as nx

from ..geospatial.geometry import normalize_text
from .graph_builder import subnet_graph

MAX_SOLVER_NODES = 12


class SubnetError(ValueError):
    pass


@dataclass
class Subnet:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    selection: dict[str, Any]
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "nodes": self.nodes,
            "edges": self.edges,
            "selection": self.selection,
            "stats": self.stats,
        }


def network_graph(network: dict[str, Any], *, available_only: bool = True) -> nx.Graph:
    return subnet_graph(network, available_only=available_only)


def component_summaries(network: dict[str, Any]) -> list[dict[str, Any]]:
    graph = network_graph(network)
    nodes = {node["id"]: node for node in network.get("nodes", [])}
    rows: list[dict[str, Any]] = []
    for index, component in enumerate(sorted(nx.connected_components(graph), key=len, reverse=True)):
        if len(component) < 2:
            continue
        sub = graph.subgraph(component)
        departments = sorted({nodes[n].get("department") for n in component if nodes[n].get("department")})
        voltages = sorted(
            {
                float(v)
                for n in component
                for v in (nodes[n].get("voltages_kv") or [nodes[n].get("voltage_kv")])
                if v is not None
            }
        )
        rows.append(
            {
                "index": len(rows),
                "nodes": len(component),
                "edges": sub.number_of_edges(),
                "total_length_km": round(sum(float(a.get("length_km") or 0) for _, _, a in sub.edges(data=True)), 3),
                "departments": departments,
                "voltages_kv": voltages,
                "node_ids": sorted(component),
            }
        )
    return rows


def _filtered_graph(
    network: dict[str, Any],
    *,
    departments: Iterable[str] | None,
    voltages: Iterable[float] | None,
) -> tuple[nx.Graph, set[str]]:
    graph = network_graph(network)
    deps = {normalize_text(d) for d in (departments or []) if d}
    volts = {float(v) for v in (voltages or []) if v is not None}
    keep_nodes = set()
    for node_id, attrs in graph.nodes(data=True):
        if deps and normalize_text(attrs.get("department")) not in deps:
            continue
        node_volts = {float(v) for v in (attrs.get("voltages_kv") or [attrs.get("voltage_kv")]) if v is not None}
        if volts and not (node_volts & volts):
            continue
        keep_nodes.add(node_id)
    filtered = nx.Graph()
    for node_id in keep_nodes:
        filtered.add_node(node_id, **graph.nodes[node_id])
    for a, b, attrs in graph.edges(data=True):
        if a not in keep_nodes or b not in keep_nodes:
            continue
        edge_volts = {float(v) for v in (attrs.get("voltages_kv") or [attrs.get("voltage_kv")]) if v is not None}
        if volts and not (edge_volts & volts):
            continue
        filtered.add_edge(a, b, **attrs)
    return filtered, keep_nodes


def _component(
    graph: nx.Graph, component_index: int | None
) -> list[str]:
    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    with_edges = [c for c in components if any(graph.degree(n) for n in c)]
    pool = with_edges or components
    if not pool:
        raise SubnetError("No hay componentes con conexiones verificadas.")
    if component_index is None:
        return sorted(pool[0])
    if component_index < 0 or component_index >= len(pool):
        raise SubnetError(f"Componente {component_index} fuera de rango (0..{len(pool) - 1}).")
    return sorted(pool[component_index])


def _grow_connected(graph: nx.Graph, component: list[str], max_nodes: int, seed_node: str | None) -> list[str]:
    if max_nodes < 2:
        raise SubnetError("Se requieren al menos 2 nodos.")
    if seed_node and seed_node not in component:
        raise SubnetError("El nodo semilla no pertenece a la componente seleccionada.")
    if not seed_node:
        seed_node = sorted(component, key=lambda n: (-graph.degree(n), graph.nodes[n].get("name", n)))[0]
    selected = {seed_node}
    heap: list[tuple[float, str]] = []
    for neighbor in graph.neighbors(seed_node):
        attrs = graph.get_edge_data(seed_node, neighbor) or {}
        heapq.heappush(heap, (float(attrs.get("length_km") or 0.0), neighbor))
    while heap and len(selected) < max_nodes:
        _, node = heapq.heappop(heap)
        if node in selected:
            continue
        selected.add(node)
        for neighbor in graph.neighbors(node):
            if neighbor in selected:
                continue
            attrs = graph.get_edge_data(node, neighbor) or {}
            heapq.heappush(heap, (float(attrs.get("length_km") or 0.0), neighbor))
    return sorted(selected)


def select_subnet(
    network: dict[str, Any],
    *,
    departments: Iterable[str] | None = None,
    voltages: Iterable[float] | None = None,
    component_index: int | None = None,
    max_nodes: int = 8,
    seed_node: str | None = None,
    node_ids: Iterable[str] | None = None,
) -> Subnet:
    """Extrae una subred inducida y conectada. No inventa aristas."""
    if max_nodes < 2:
        raise SubnetError("max_nodes debe ser ≥ 2.")
    graph, _ = _filtered_graph(network, departments=departments, voltages=voltages)
    requested_ids = list(dict.fromkeys(node_ids or []))
    if requested_ids:
        missing = [node for node in requested_ids if node not in graph]
        if missing:
            raise SubnetError(f"Nodos inexistentes o filtrados: {missing}")
        selected = sorted(set(requested_ids))
        pool_size = len(selected)
    else:
        component = _component(graph, component_index)
        selected = _grow_connected(graph, component, max_nodes, seed_node)
        pool_size = len(component)

    sub = graph.subgraph(selected)
    if not nx.is_connected(sub):
        raise SubnetError("La selección no es una subred conectada. Ajuste filtros o semilla.")

    node_map = {node["id"]: node for node in network.get("nodes", [])}
    edge_map: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in network.get("edges", []):
        if edge.get("validation") != "verified_endpoint_attributes":
            continue
        edge_map[tuple(sorted((edge["source"], edge["target"])))] = edge

    nodes = []
    for node_id in sorted(selected):
        original = node_map.get(node_id, dict(sub.nodes[node_id]))
        nodes.append(
            {
                **original,
                "id": node_id,
                "provenance": "OFICIAL",
                "identity_provenance": "DERIVADO",
                "selection_role": "seed" if node_id == seed_node else "member",
            }
        )
    edges = []
    for a, b in sorted(sub.edges()):
        edge = edge_map.get(tuple(sorted((a, b))))
        if edge is None:
            raise SubnetError("Una arista de la subred no conserva su registro de procedencia.")
        edges.append({**edge, "available": True, "failed": False})
    if not edges:
        raise SubnetError("La subred seleccionada no contiene conexiones verificadas.")

    total_length = sum(float(edge.get("length_km") or 0.0) for edge in edges)
    selection = {
        "departments": sorted({normalize_text(d) for d in (departments or [])}),
        "voltages_kv": sorted({float(v) for v in (voltages or [])}),
        "component_index": component_index,
        "max_nodes": max_nodes,
        "seed_node": seed_node,
        "requested_nodes": requested_ids or None,
        "actual_nodes": len(nodes),
        "truncated": bool(not requested_ids and len(nodes) < pool_size),
        "pool_nodes": pool_size,
        "verified_only": True,
        "message": (
            f"Subred conectada de {len(nodes)} nodos y {len(edges)} conexiones verificadas."
            if len(nodes) >= max_nodes
            else f"La componente solo permitió {len(nodes)} nodos conectados (solicitado {max_nodes})."
        ),
    }
    stats = {
        "nodes": len(nodes),
        "edges": len(edges),
        "total_length_km": round(total_length, 4),
        "voltages_kv": sorted({float(e["voltage_kv"]) for e in edges if e.get("voltage_kv") is not None}),
        "departments": sorted({n.get("department") for n in nodes if n.get("department")}),
        "components": 1,
        "bridges": [list(edge) for edge in nx.bridges(sub)],
        "cycle_basis_size": len(nx.cycle_basis(sub)),
    }
    return Subnet(nodes=nodes, edges=edges, selection=selection, stats=stats)


def availability_by_size(
    network: dict[str, Any],
    sizes: Iterable[int] = (4, 6, 8, 10, 12),
    *,
    departments: Iterable[str] | None = None,
    voltages: Iterable[float] | None = None,
) -> dict[int, dict[str, Any]]:
    graph, _ = _filtered_graph(network, departments=departments, voltages=voltages)
    components = [c for c in nx.connected_components(graph) if any(graph.degree(n) for n in c)]
    largest = max((len(c) for c in components), default=0)
    return {
        int(size): {
            "available": largest >= int(size),
            "largest_component": largest,
            "message": (
                f"Disponible en una componente de {largest} nodos."
                if largest >= int(size)
                else f"No hay componente conectada de {size} nodos (máximo {largest})."
            ),
        }
        for size in sizes
    }


def subnet_to_json(subnet: Subnet | dict[str, Any]) -> str:
    payload = subnet.to_dict() if isinstance(subnet, Subnet) else subnet
    return json.dumps(payload, ensure_ascii=False, indent=2)
