"""Genera los activos GeoJSON/JSON que consume el frontend React.

Uso:
    python -m scripts.export_frontend_data

Salida:
    frontend/public/data/summary.json
    frontend/public/data/components.json
    frontend/public/data/stations-index.json
    frontend/public/data/map/stations.geojson
    frontend/public/data/map/lines.geojson
    frontend/public/data/map/edges.geojson
    frontend/public/data/map/generation.geojson
    frontend/public/data/experiment.json
    frontend/public/data/manifest.json
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from src.models.graph_model import ROOT
from src.network.graph_builder import load_network_snapshot
from src.network.subnet_selector import availability_by_size, component_summaries

OUT = ROOT / "frontend" / "public" / "data"


def _round_coords(value: Any, digits: int = 5) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), digits)
    if isinstance(value, (list, tuple)):
        return [_round_coords(item, digits) for item in value]
    return value


def _geometry(geometry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not geometry:
        return None
    return {
        "type": geometry.get("type"),
        "coordinates": _round_coords(geometry.get("coordinates")),
    }


def _write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")


def _kv(value: Any) -> float | None:
    """Redondea tensiones a 2 decimales para eliminar ruido tipo 22.89999962."""
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _count_key(value: Any) -> str:
    """Normaliza 500.0 -> "500" para que la UI compare tensiones sin ambigüedad."""
    if isinstance(value, (int, float)):
        number = round(float(value), 2)
        return str(int(number)) if number.is_integer() else str(number)
    return str(value)


def _counts(values: Any) -> dict[str, int]:
    counter = Counter(_count_key(value) for value in values if value is not None)
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _feature(geometry: dict[str, Any] | None, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": _geometry(geometry),
        "properties": properties,
    }


def build(network: dict[str, Any]) -> dict[str, Any]:
    nodes = network.get("nodes", [])
    edges = network.get("edges", [])
    lines = network.get("lines", [])
    generation = network.get("generation", [])
    node_map = {node["id"]: node for node in nodes}

    OUT.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Resumen ejecutivo
    # ------------------------------------------------------------------
    quality = dict(network.get("quality", {}) or {})
    quality.pop("isolated_node_ids", None)
    source = network.get("source", {}) or {}
    metadata = source.get("source_metadata", {}) or {}
    components = component_summaries(network)
    for row in components:
        row["label"] = f"Componente {row['index'] + 1}"
        row["sample_names"] = [
            node_map[node_id]["name"]
            for node_id in row.get("node_ids", [])[:4]
            if node_id in node_map
        ]
    top_stations = sorted(
        nodes,
        key=lambda node: (-int(node.get("verified_degree") or 0), node.get("name", "")),
    )[:12]
    summary = {
        "generated_at_utc": network.get("generated_at_utc"),
        "source": {
            "institution": source.get("institution", "OSINERGMIN"),
            "service": source.get("service"),
            "downloaded_at_utc": metadata.get("downloaded_at_utc"),
            "provenance": metadata.get("provenance", "OFICIAL"),
            "classification_note": metadata.get("classification_note"),
            "layers": [
                {
                    "layer_id": target.get("layer_id"),
                    "name": target.get("name"),
                    "role": target.get("role"),
                    "geometry_type": target.get("geometry_type"),
                    "voltage_kv": target.get("voltage_kv"),
                }
                for target in metadata.get("targets", [])
            ],
        },
        "metadata": network.get("metadata", {}),
        "quality": quality,
        "counts": {
            "stations": len(nodes),
            "stations_in_verified_graph": quality.get("nodes_in_verified_graph", 0),
            "lines": len(lines),
            "lines_verified": sum(
                1 for line in lines if line.get("connectivity_status") == "verified"
            ),
            "lines_unverified": sum(
                1 for line in lines if line.get("connectivity_status") != "verified"
            ),
            "edges": len(edges),
            "components_with_edges": quality.get("components_with_edges", 0),
            "generation": len(generation),
            "coes_validated_edges": sum(
                1 for edge in edges if edge.get("coes_validated")
            ),
        },
        "voltage_counts": {
            "stations": _counts(node.get("voltage_kv") for node in nodes),
            "edges": _counts(edge.get("voltage_kv") for edge in edges),
            "lines": _counts(line.get("voltage_kv") for line in lines),
        },
        "department_counts": _counts(node.get("department") for node in nodes),
        "line_status_counts": _counts(
            line.get("connectivity_status") for line in lines
        ),
        "components": components,
        "top_stations": [
            {
                "id": node["id"],
                "name": node.get("name"),
                "voltage_kv": _kv(node.get("voltage_kv")),
                "department": node.get("department"),
                "degree": node.get("verified_degree", 0),
                "lon": node.get("lon"),
                "lat": node.get("lat"),
            }
            for node in top_stations
        ],
        "availability": availability_by_size(network, (4, 6, 8, 10, 12)),
    }
    _write_json(OUT / "summary.json", summary, pretty=True)
    _write_json(OUT / "components.json", {"components": components}, pretty=True)
    _write_json(
        OUT / "stations-index.json",
        {
            "stations": [
                {
                    "id": node["id"],
                    "name": node.get("name"),
                    "voltage_kv": _kv(node.get("voltage_kv")),
                    "department": node.get("department"),
                    "company": node.get("company"),
                    "degree": node.get("verified_degree", 0),
                    "lon": node.get("lon"),
                    "lat": node.get("lat"),
                }
                for node in nodes
            ]
        },
    )

    # ------------------------------------------------------------------
    # Estaciones
    # ------------------------------------------------------------------
    station_features = []
    for node in nodes:
        station_features.append(
            _feature(
                node.get("geometry"),
                {
                    "id": node["id"],
                    "name": node.get("name"),
                    "lon": node.get("lon"),
                    "lat": node.get("lat"),
                    "kv": _kv(node.get("voltage_kv")),
                    "voltages": [_kv(value) for value in node.get("voltages_kv", [])],
                    "department": node.get("department"),
                    "province": node.get("province"),
                    "company": node.get("company"),
                    "capacity_mva": node.get("capacity_mva"),
                    "operational": node.get("operational"),
                    "in_graph": node.get("in_verified_graph", False),
                    "degree": node.get("verified_degree", 0),
                    "type": node.get("node_type", "substation"),
                    "provenance": node.get("provenance", "OFICIAL"),
                },
            )
        )
    _write_json(
        OUT / "map" / "stations.geojson",
        {"type": "FeatureCollection", "features": station_features},
    )

    # ------------------------------------------------------------------
    # Líneas: todas las geometrías oficiales. La UI las separa por estado.
    # ------------------------------------------------------------------
    line_features = []
    for line in lines:
        from_node = node_map.get(line.get("endpoint_from") or "")
        to_node = node_map.get(line.get("endpoint_to") or "")
        departments = sorted(
            {
                value
                for value in (
                    (from_node or {}).get("department"),
                    (to_node or {}).get("department"),
                )
                if value
            }
        )
        line_features.append(
            _feature(
                line.get("geometry"),
                {
                    "id": line.get("source_id"),
                    "name": line.get("name"),
                    "kv": _kv(line.get("voltage_kv")),
                    "status": line.get("connectivity_status"),
                    "verified": line.get("connectivity_status") == "verified",
                    "from_name": line.get("from_name"),
                    "to_name": line.get("to_name"),
                    "from_id": line.get("endpoint_from"),
                    "to_id": line.get("endpoint_to"),
                    "departments": departments,
                    "length_km": line.get("length_km"),
                    "company": line.get("company"),
                    "system": line.get("system"),
                    "area_sein": line.get("area_sein"),
                    "circuit_type": line.get("circuit_type"),
                    "conductor": line.get("conductor"),
                    "coes_validated": bool(line.get("coes_validated")),
                },
            )
        )
    _write_json(
        OUT / "map" / "lines.geojson",
        {"type": "FeatureCollection", "features": line_features},
    )

    # ------------------------------------------------------------------
    # Aristas verificadas
    # ------------------------------------------------------------------
    edge_features = []
    for edge in edges:
        departments = sorted(
            {
                value
                for value in (
                    (node_map.get(edge["source"]) or {}).get("department"),
                    (node_map.get(edge["target"]) or {}).get("department"),
                )
                if value
            }
        )
        edge_features.append(
            _feature(
                edge.get("geometry"),
                {
                    "id": edge["id"],
                    "source": edge["source"],
                    "target": edge["target"],
                    "source_name": edge.get("source_name"),
                    "target_name": edge.get("target_name"),
                    "kv": _kv(edge.get("voltage_kv")),
                    "length_km": edge.get("length_km"),
                    "line_count": edge.get("line_count"),
                    "parallel": edge.get("parallel"),
                    "departments": departments,
                    "validation": edge.get("validation"),
                    "coes_validated": bool(edge.get("coes_validated")),
                    "line_names": edge.get("line_names", []),
                },
            )
        )
    _write_json(
        OUT / "map" / "edges.geojson",
        {"type": "FeatureCollection", "features": edge_features},
    )

    # ------------------------------------------------------------------
    # Centrales de generación
    # ------------------------------------------------------------------
    generation_features = []
    for plant in generation:
        generation_features.append(
            _feature(
                plant.get("geometry"),
                {
                    "id": plant.get("source_id"),
                    "name": plant.get("name"),
                    "kv": _kv(plant.get("voltage_kv")),
                    "technology": plant.get("technology"),
                    "capacity_installed_mw": plant.get("capacity_installed_mw"),
                    "capacity_effective_mw": plant.get("capacity_effective_mw"),
                    "company": plant.get("company"),
                    "department": plant.get("department"),
                    "province": plant.get("province"),
                    "state": plant.get("state"),
                    "provenance": plant.get("provenance", "OFICIAL"),
                },
            )
        )
    _write_json(
        OUT / "map" / "generation.geojson",
        {"type": "FeatureCollection", "features": generation_features},
    )

    # ------------------------------------------------------------------
    # Artefacto de experimento reproducible
    # ------------------------------------------------------------------
    experiment_path = ROOT / "results" / "real_subnet_experiment.json"
    if experiment_path.exists():
        _write_json(
            OUT / "experiment.json",
            json.loads(experiment_path.read_text(encoding="utf-8")),
            pretty=True,
        )

    manifest = {
        "generated_at_utc": summary["generated_at_utc"],
        "counts": summary["counts"],
        "files": {
            "summary": "summary.json",
            "components": "components.json",
            "stations_index": "stations-index.json",
            "stations": "map/stations.geojson",
            "lines": "map/lines.geojson",
            "edges": "map/edges.geojson",
            "generation": "map/generation.geojson",
            "experiment": "experiment.json",
        },
    }
    _write_json(OUT / "manifest.json", manifest, pretty=True)
    return manifest


def main() -> int:
    network = load_network_snapshot()
    manifest = build(network)
    print("Activos del frontend generados en:", OUT)
    for key, value in manifest["counts"].items():
        print(f"  {key}: {value}")
    for path in sorted(OUT.rglob("*")):
        if path.is_file():
            print(f"  {path.relative_to(OUT)} · {path.stat().st_size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
