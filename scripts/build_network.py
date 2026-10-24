"""Procesa el snapshot crudo y construye el grafo verificado del SEIN.

Uso:
    python -m scripts.build_network
    python -m scripts.build_network --force   # vuelve a descargar antes
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.data_sources.arcgis import ArcGISClient
from src.data_sources.osinergmin import RAW_DIR, SERVICE_URL, download_sein, load_snapshot
from src.geospatial.processing import PROCESSED_DIR, process_snapshot, save_processed
from src.network.graph_builder import NETWORK_DIR, build_network, save_network


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument("--processed-dir", default=str(PROCESSED_DIR))
    parser.add_argument("--network-dir", default=str(NETWORK_DIR))
    args = parser.parse_args(argv)

    if args.force_download:
        download_sein(client=ArcGISClient(SERVICE_URL), raw_dir=args.raw_dir, force=True)

    try:
        snapshot = load_snapshot(args.raw_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    processed = process_snapshot(snapshot)
    save_processed(processed, args.processed_dir)
    network = build_network(processed, source_metadata=snapshot)
    path = save_network(network, args.network_dir)

    quality = network["quality"]
    print(f"Red guardada: {path}")
    print(
        f"Estaciones: {quality['nodes_total']} · en grafo verificado: {quality['nodes_in_verified_graph']} "
        f"· aisladas: {quality['nodes_isolated']}"
    )
    print(
        f"Líneas: {quality['lines_total']} · verificadas: {quality['lines_verified']} "
        f"· no verificadas: {quality['lines_unverified']}"
    )
    print(
        f"Aristas agregadas: {quality['edges_verified']} · componentes: {quality['components_verified']} "
        f"· mayor componente: {quality['largest_component_nodes']} nodos"
    )
    print("Estados de líneas:", json.dumps(quality["line_status"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
