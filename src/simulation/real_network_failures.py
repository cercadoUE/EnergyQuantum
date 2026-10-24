"""Fallas sobre la red real: topología y métricas sin inventar suministro."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any, Iterable

import networkx as nx

from ..network.subnet_selector import network_graph


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fail_edges(subnet: dict[str, Any] | Any, edge_ids: Iterable[str]) -> dict[str, Any]:
    payload = subnet.to_dict() if hasattr(subnet, "to_dict") else deepcopy(subnet)
    requested = {str(edge_id) for edge_id in edge_ids}
    known = {str(edge["id"]) for edge in payload.get("edges", [])}
    missing = sorted(requested - known)
    if missing:
        raise ValueError(f"Conexiones inexistentes en la subred: {missing}")
    for edge in payload.get("edges", []):
        if str(edge["id"]) in requested:
            edge["failed"] = True
    payload["scenario"] = {
        "failed_edge_ids": sorted(requested),
        "applied_at_utc": utc_now(),
        "note": "Falla topológica simulada; no implica pérdida de suministro.",
    }
    return payload


def subnet_metrics(
    subnet: dict[str, Any] | Any,
    *,
    include_failed: bool = True,
    bits: list[int] | None = None,
    instance: Any | None = None,
) -> dict[str, Any]:
    payload = subnet.to_dict() if hasattr(subnet, "to_dict") else subnet
    graph = nx.Graph()
    for node in payload.get("nodes", []):
        graph.add_node(node["id"], **node)
    failed = [edge for edge in payload.get("edges", []) if edge.get("failed")]
    active = [
        edge
        for edge in payload.get("edges", [])
        if include_failed or (not edge.get("failed") and edge.get("available", True))
    ]
    for edge in active:
        graph.add_edge(edge["source"], edge["target"], **edge)
    if bits is not None and instance is not None:
        data = instance.to_solver_data()
        index = data.get("instance_metadata", {}).get("id_map", {})
        for edge in data["edges"]:
            if bits[edge["source"]] != bits[edge["target"]]:
                a = next(key for key, value in index.items() if value == edge["source"])
                b = next(key for key, value in index.items() if value == edge["target"])
                if graph.has_edge(a, b):
                    graph.remove_edge(a, b)

    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    configured_length = sum(
        float(edge.get("length_km") or 0) for edge in payload.get("edges", [])
    )
    active_length = sum(
        float(graph.get_edge_data(a, b, {}).get("length_km") or 0)
        for a, b in graph.edges()
    )
    return {
        "nodes": graph.number_of_nodes(),
        "edges_configured": len(payload.get("edges", [])),
        "edges_active": graph.number_of_edges(),
        "edges_failed": len(failed),
        "failed_edge_ids": sorted(str(edge["id"]) for edge in failed),
        "components": len(components),
        "largest_component": max((len(c) for c in components), default=0),
        "isolated_nodes": sum(1 for _, degree in graph.degree() if degree == 0),
        "total_length_km_configured": round(configured_length, 4),
        "total_length_km_active": round(active_length, 4),
        "bridges": [list(edge) for edge in nx.bridges(graph)] if graph.number_of_edges() else [],
        "articulation_points": sorted(nx.articulation_points(graph)) if graph.number_of_nodes() else [],
        "served_demand": None,
        "lost_demand": None,
        "note": (
            "Una componente conectada no certifica suministro. No hay demanda, "
            "generación, flujo ni protecciones modeladas."
        ),
        "computed_at_utc": utc_now(),
    }


def compare_metrics(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "edges_active",
        "edges_failed",
        "components",
        "largest_component",
        "isolated_nodes",
        "total_length_km_active",
        "served_demand",
    ]
    return {
        "before": {key: before.get(key) for key in keys},
        "after": {key: after.get(key) for key in keys},
        "delta": {
            key: (
                None
                if before.get(key) is None or after.get(key) is None
                else after.get(key) - before.get(key)
            )
            for key in keys
        },
        "note": "Cambios topológicos observados. No se calcula energía no suministrada.",
    }


def network_failure_report(
    network: dict[str, Any],
    edge_ids: Iterable[str],
) -> dict[str, Any]:
    """Aplica fallas sobre la red nacional verificada y reporta componentes."""
    graph = network_graph(network)
    requested = {str(edge_id) for edge_id in edge_ids}
    known = {str(edge.get("id")) for edge in network.get("edges", [])}
    missing = sorted(requested - known)
    if missing:
        raise ValueError(f"Aristas inexistentes: {missing}")
    before = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "components": nx.number_connected_components(graph),
        "largest_component": max((len(c) for c in nx.connected_components(graph)), default=0),
    }
    graph.remove_edges_from(
        [
            (edge["source"], edge["target"])
            for edge in network.get("edges", [])
            if str(edge.get("id")) in requested
        ]
    )
    after = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "components": nx.number_connected_components(graph),
        "largest_component": max((len(c) for c in nx.connected_components(graph)), default=0),
        "isolated": sorted(node for node, degree in graph.degree() if degree == 0),
    }
    return {
        "failed_edge_ids": sorted(requested),
        "before": before,
        "after": after,
        "generated_at_utc": utc_now(),
        "limitations": [
            "No se estima energía no suministrada.",
            "No se modelan protecciones, flujo, frecuencia ni re-despacho.",
        ],
    }
