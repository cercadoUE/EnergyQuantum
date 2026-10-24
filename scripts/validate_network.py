"""Audita integridad del snapshot y de la topología derivada.

Uso:
    python -m scripts.validate_network
"""
from __future__ import annotations

import argparse
import json
import sys

from src.data_sources.osinergmin import RAW_DIR, snapshot_quality
from src.network.graph_builder import NETWORK_DIR, load_network_snapshot, subnet_graph
from src.network.subnet_selector import availability_by_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument("--network-dir", default=str(NETWORK_DIR))
    args = parser.parse_args(argv)

    snapshot = snapshot_quality(args.raw_dir)
    network = load_network_snapshot(args.network_dir)
    graph = subnet_graph(network, available_only=False)
    node_ids = {node["id"] for node in network["nodes"]}
    problems: list[str] = []
    checks = {
        "snapshot_ok": snapshot["ok"],
        "verified_edges": len(network["edges"]),
        "nodes": len(network["nodes"]),
        "nodes_in_verified_graph": network["quality"]["nodes_in_verified_graph"],
    }
    if not snapshot["ok"]:
        problems.extend(snapshot["problems"])
    if not network["edges"]:
        problems.append("No hay conexiones verificadas.")
    for edge in network["edges"]:
        if edge.get("validation") != "verified_endpoint_attributes":
            problems.append(f"Arista sin validación esperada: {edge.get('id')}")
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            problems.append(f"Arista con extremo inexistente: {edge['id']}")
        if edge["source"] == edge["target"]:
            problems.append(f"Autoenlace: {edge['id']}")
        if not edge.get("length_km") or edge["length_km"] <= 0:
            problems.append(f"Longitud no positiva: {edge['id']}")
        if edge.get("coes_validated"):
            problems.append(f"Arista declara COES sin evidencia: {edge['id']}")
    if len(node_ids) != len({node["id"] for node in network["nodes"]}):
        problems.append("IDs de nodo duplicados.")
    if graph.number_of_edges() != len(network["edges"]):
        problems.append("El grafo reconstruido no conserva todas las aristas.")
    availability = availability_by_size(network, (4, 6, 8, 10, 12))
    checks["subnet_availability"] = availability
    checks["connected_components_with_edges"] = network["quality"]["components_with_edges"]
    checks["largest_component_nodes"] = network["quality"]["largest_component_nodes"]

    print(json.dumps({"checks": checks, "problems": problems}, ensure_ascii=False, indent=2))
    if problems:
        print(f"FALLO: {len(problems)} problema(s).", file=sys.stderr)
        return 1
    print("OK: snapshot y topología consistentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
