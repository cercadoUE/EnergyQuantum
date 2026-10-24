"""QuantumGrid Perú · API de datos reales, subredes y optimización.

Ejecutar en desarrollo:
    python -m uvicorn api.main:app --reload --port 8000

La API reutiliza el snapshot procesado y los mismos módulos que la app
Streamlit. No descarga datos en tiempo de ejecución ni inventa conexiones.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.algorithms.classical import brute_force, kernighan_lin, local_search
from src.algorithms.qaoa_solver import solve as qaoa_solve
from src.models.graph_model import ROOT, load_network as load_synthetic_network
from src.models.objective import Objective
from src.models.optimization_instance import (
    DEMAND_MODES,
    WEIGHT_MODES,
    InstanceError,
    build_instance,
)
from src.network.graph_builder import load_network_snapshot
from src.network.subnet_selector import (
    SubnetError,
    availability_by_size,
    component_summaries,
    select_subnet,
)
from src.simulation.real_network_failures import (
    compare_metrics,
    fail_edges,
    network_failure_report,
    subnet_metrics,
)

PROCESSED_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results"
DIST_DIR = ROOT / "frontend" / "dist"

app = FastAPI(
    title="QuantumGrid Perú API",
    version="1.0.0",
    description=(
        "Red eléctrica del SEIN derivada de OSINERGMIN, selección de subredes "
        "verificadas y ejecución de solucionadores clásicos/QAOA."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    """Convierte escalares NumPy y estructuras anidadas a JSON estándar."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


@lru_cache(maxsize=1)
def network() -> dict[str, Any]:
    return load_network_snapshot()


def _node_index() -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in network().get("nodes", [])}


def _count_key(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _counts(values: Iterable[Any]) -> dict[str, int]:
    counter = Counter(_count_key(value) for value in values if value is not None)
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _source_brief() -> dict[str, Any]:
    source = network().get("source", {}) or {}
    metadata = source.get("source_metadata", {}) or {}
    return {
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
    }


def _quality_brief() -> dict[str, Any]:
    quality = dict(network().get("quality", {}) or {})
    quality.pop("isolated_node_ids", None)
    return quality


def _component_rows() -> list[dict[str, Any]]:
    rows = component_summaries(network())
    nodes = _node_index()
    for row in rows:
        row["label"] = f"Componente {row['index'] + 1}"
        row["sample_names"] = [
            nodes[node_id]["name"]
            for node_id in row.get("node_ids", [])[:4]
            if node_id in nodes
        ]
    return rows


def _subnet_payload(
    *,
    component_index: int | None,
    max_nodes: int,
    departments: list[str] | None,
    voltages: list[float] | None,
    seed_node: str | None,
    node_ids: list[str] | None,
) -> tuple[dict[str, Any], Any]:
    subnet = select_subnet(
        network(),
        component_index=component_index,
        max_nodes=max_nodes,
        departments=departments or None,
        voltages=voltages or None,
        seed_node=seed_node,
        node_ids=node_ids or None,
    )
    return subnet.to_dict(), subnet


def _partition_from_bits(
    bits: list[int] | None, id_map: dict[str, int]
) -> dict[str, Any] | None:
    if bits is None:
        return None
    groups: dict[str, list[str]] = {"A": [], "B": []}
    assignment: dict[str, int] = {}
    for node_id, index in id_map.items():
        value = int(bits[index])
        assignment[node_id] = value
        groups["B" if value else "A"].append(node_id)
    return {
        "assignment": assignment,
        "groups": {key: sorted(value) for key, value in groups.items()},
    }


def _bridge_edges(subnet: dict[str, Any]) -> list[dict[str, Any]]:
    edge_by_pair = {
        tuple(sorted((edge["source"], edge["target"]))): edge
        for edge in subnet.get("edges", [])
    }
    rows = []
    for pair in subnet.get("stats", {}).get("bridges", []):
        edge = edge_by_pair.get(tuple(sorted(pair)))
        if edge:
            rows.append(
                {
                    "id": edge["id"],
                    "source": edge["source"],
                    "target": edge["target"],
                    "source_name": edge.get("source_name"),
                    "target_name": edge.get("target_name"),
                    "length_km": edge.get("length_km"),
                    "voltage_kv": edge.get("voltage_kv"),
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Modelos de entrada
# ---------------------------------------------------------------------------


class SubnetConfig(BaseModel):
    component_index: int | None = 0
    max_nodes: int = Field(6, ge=2, le=12)
    departments: list[str] = Field(default_factory=list)
    voltages: list[float] = Field(default_factory=list)
    seed_node: str | None = None
    node_ids: list[str] | None = None


class OptimizeRequest(SubnetConfig):
    weight_mode: str = "length"
    demand_mode: str = "uniform"
    demand_value: float = Field(1.0, gt=0)
    seed: int = 7
    alpha: float = Field(1.0, ge=0)
    beta: float = Field(3.0, gt=0)
    algorithms: list[str] = Field(
        default_factory=lambda: ["Exacto", "Búsqueda local", "Kernighan–Lin", "QAOA"]
    )
    restarts: int = Field(12, ge=1, le=100)
    qaoa_p: int = Field(1, ge=1, le=4)
    qaoa_shots: int = Field(2048, ge=1, le=100000)
    qaoa_maxiter: int = Field(60, ge=1, le=300)
    qaoa_time_limit: float = Field(60.0, gt=0, le=600)
    qaoa_max_evaluations: int = Field(400, ge=1, le=5000)
    failed_edge_ids: list[str] = Field(default_factory=list)


class FailureRequest(SubnetConfig):
    failed_edge_ids: list[str] = Field(default_factory=list)


class NetworkFailureRequest(BaseModel):
    edge_ids: list[str] = Field(default_factory=list)


class SyntheticRequest(BaseModel):
    nodes: int = Field(12, ge=4, le=12)
    seed: int = 7
    alpha: float = Field(1.0, ge=0)
    beta: float = Field(3.0, gt=0)
    algorithms: list[str] = Field(
        default_factory=lambda: ["Exacto", "Búsqueda local", "Kernighan–Lin", "QAOA"]
    )
    restarts: int = Field(12, ge=1, le=100)
    qaoa_p: int = Field(1, ge=1, le=4)
    qaoa_shots: int = Field(2048, ge=1, le=100000)
    qaoa_maxiter: int = Field(60, ge=1, le=300)
    qaoa_time_limit: float = Field(60.0, gt=0, le=600)
    qaoa_max_evaluations: int = Field(400, ge=1, le=5000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, Any]:
    net = network()
    return {
        "status": "ok",
        "nodes": len(net.get("nodes", [])),
        "edges": len(net.get("edges", [])),
        "lines": len(net.get("lines", [])),
        "snapshot_generated_at_utc": net.get("generated_at_utc"),
    }


@app.get("/api/network/summary")
def network_summary() -> dict[str, Any]:
    net = network()
    nodes = net.get("nodes", [])
    edges = net.get("edges", [])
    lines = net.get("lines", [])
    quality = _quality_brief()
    components = _component_rows()
    top_stations = sorted(
        nodes,
        key=lambda node: (-int(node.get("verified_degree") or 0), node.get("name", "")),
    )[:12]
    return _json_safe(
        {
            "generated_at_utc": net.get("generated_at_utc"),
            "source": _source_brief(),
            "metadata": net.get("metadata", {}),
            "quality": quality,
            "counts": {
                "stations": len(nodes),
                "stations_in_verified_graph": quality.get(
                    "nodes_in_verified_graph", 0
                ),
                "lines": len(lines),
                "lines_verified": sum(
                    1
                    for line in lines
                    if line.get("connectivity_status") == "verified"
                ),
                "lines_unverified": sum(
                    1
                    for line in lines
                    if line.get("connectivity_status") != "verified"
                ),
                "edges": len(edges),
                "components_with_edges": quality.get("components_with_edges", 0),
                "generation": len(net.get("generation", [])),
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
                    "voltage_kv": node.get("voltage_kv"),
                    "department": node.get("department"),
                    "degree": node.get("verified_degree", 0),
                    "lon": node.get("lon"),
                    "lat": node.get("lat"),
                }
                for node in top_stations
            ],
            "availability": availability_by_size(net, (4, 6, 8, 10, 12)),
            "scenarios": {"weights": WEIGHT_MODES, "demand": DEMAND_MODES},
        }
    )


@app.get("/api/network/components")
def network_components() -> dict[str, Any]:
    return {"components": _json_safe(_component_rows())}


@app.get("/api/network/stations")
def search_stations(
    q: str = Query("", max_length=120),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    term = q.strip().upper()
    rows = []
    for node in network().get("nodes", []):
        if term and term not in str(node.get("name", "")).upper():
            continue
        rows.append(
            {
                "id": node["id"],
                "name": node.get("name"),
                "voltage_kv": node.get("voltage_kv"),
                "department": node.get("department"),
                "company": node.get("company"),
                "degree": node.get("verified_degree", 0),
                "lon": node.get("lon"),
                "lat": node.get("lat"),
            }
        )
    rows.sort(key=lambda row: (-int(row["degree"] or 0), row["name"] or ""))
    return {"stations": rows[:limit], "total": len(rows)}


@app.get("/api/network/edges")
def search_edges(
    q: str = Query("", max_length=120),
    limit: int = Query(40, ge=1, le=200),
) -> dict[str, Any]:
    term = q.strip().upper()
    rows = []
    for edge in network().get("edges", []):
        haystack = f"{edge.get('source_name', '')} {edge.get('target_name', '')} {edge.get('line_names', [])}".upper()
        if term and term not in haystack:
            continue
        rows.append(
            {
                "id": edge["id"],
                "source": edge["source"],
                "target": edge["target"],
                "source_name": edge.get("source_name"),
                "target_name": edge.get("target_name"),
                "length_km": edge.get("length_km"),
                "voltage_kv": edge.get("voltage_kv"),
                "line_count": edge.get("line_count"),
                "parallel": edge.get("parallel"),
                "validation": edge.get("validation"),
            }
        )
    rows.sort(key=lambda row: (-float(row["length_km"] or 0), row["source_name"] or ""))
    return {"edges": rows[:limit], "total": len(rows)}


@app.get("/api/subnet")
def subnet_preview(
    component_index: int | None = 0,
    max_nodes: int = Query(6, ge=2, le=12),
    departments: str | None = None,
    voltages: str | None = None,
    seed_node: str | None = None,
) -> dict[str, Any]:
    try:
        payload, subnet = _subnet_payload(
            component_index=component_index,
            max_nodes=max_nodes,
            departments=[item for item in (departments or "").split(",") if item],
            voltages=[float(item) for item in (voltages or "").split(",") if item],
            seed_node=seed_node,
            node_ids=None,
        )
    except (SubnetError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _json_safe(
        {
            "subnet": payload,
            "metrics": subnet_metrics(payload, include_failed=False),
            "bridge_edges": _bridge_edges(payload),
            "component": subnet.selection.get("component_index"),
        }
    )


@app.post("/api/optimize")
def optimize(request: OptimizeRequest) -> dict[str, Any]:
    started = perf_counter()
    try:
        payload, subnet = _subnet_payload(
            component_index=request.component_index,
            max_nodes=request.max_nodes,
            departments=request.departments,
            voltages=request.voltages,
            seed_node=request.seed_node,
            node_ids=request.node_ids,
        )
        instance = build_instance(
            payload,
            weight_mode=request.weight_mode,
            demand_mode=request.demand_mode,
            demand_value=request.demand_value,
            seed=request.seed,
            failed_edge_ids=request.failed_edge_ids,
        )
        data = instance.to_solver_data()
        objective = Objective(alpha=request.alpha, beta=request.beta)
        id_map = data["instance_metadata"]["id_map"]
        runs: dict[str, Any] = {}
        for name in request.algorithms:
            if name == "Exacto":
                runs[name] = brute_force(data, objective)
            elif name == "Búsqueda local":
                runs[name] = local_search(
                    data, objective, seed=request.seed, restarts=request.restarts
                )
            elif name == "Kernighan–Lin":
                runs[name] = kernighan_lin(
                    data, objective, seed=request.seed, restarts=request.restarts
                )
            elif name == "QAOA":
                runs[name] = qaoa_solve(
                    data,
                    objective,
                    p=request.qaoa_p,
                    maxiter=request.qaoa_maxiter,
                    shots=request.qaoa_shots,
                    seed=request.seed,
                    optimizer="COBYLA",
                    time_limit=request.qaoa_time_limit,
                    max_evaluations=request.qaoa_max_evaluations,
                )
            else:
                raise HTTPException(
                    status_code=400, detail=f"Algoritmo no soportado: {name}"
                )
    except (SubnetError, InstanceError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for run in runs.values():
        run["partition"] = _partition_from_bits(run.get("bits"), id_map)

    return _json_safe(
        {
            "subnet": payload,
            "instance": instance.to_dict(),
            "id_map": id_map,
            "objective": {"alpha": request.alpha, "beta": request.beta},
            "config": request.model_dump(),
            "runs": runs,
            "metrics": subnet_metrics(payload, include_failed=False),
            "bridge_edges": _bridge_edges(payload),
            "elapsed_seconds": round(perf_counter() - started, 4),
        }
    )


@app.post("/api/failure")
def simulate_failure(request: FailureRequest) -> dict[str, Any]:
    if not request.failed_edge_ids:
        raise HTTPException(status_code=400, detail="Seleccione al menos una conexión.")
    try:
        payload, subnet = _subnet_payload(
            component_index=request.component_index,
            max_nodes=request.max_nodes,
            departments=request.departments,
            voltages=request.voltages,
            seed_node=request.seed_node,
            node_ids=request.node_ids,
        )
        before = subnet_metrics(payload, include_failed=False)
        failed_payload = fail_edges(payload, request.failed_edge_ids)
        after = subnet_metrics(failed_payload, include_failed=False)
        comparison = compare_metrics(before, after)
    except (SubnetError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    details = [
        edge for edge in payload["edges"] if edge["id"] in set(request.failed_edge_ids)
    ]
    return _json_safe(
        {
            "subnet": payload,
            "failed_subnet": failed_payload,
            "before": before,
            "after": after,
            "comparison": comparison,
            "failed_edges": details,
            "bridge_edges": _bridge_edges(payload),
        }
    )


@app.post("/api/failure/network")
def simulate_network_failure(request: NetworkFailureRequest) -> dict[str, Any]:
    if not request.edge_ids:
        raise HTTPException(status_code=400, detail="Seleccione al menos una conexión.")
    try:
        report = network_failure_report(network(), request.edge_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _json_safe(report)


@app.get("/api/experiment")
def experiment() -> dict[str, Any]:
    path = RESULTS_DIR / "real_subnet_experiment.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="No existe results/real_subnet_experiment.json. Ejecute scripts.run_real_experiment.",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/synthetic/network")
def synthetic_network(nodes: int = Query(12, ge=4, le=12)) -> dict[str, Any]:
    data = load_synthetic_network(nodes)
    return _json_safe({"network": data, "nodes": nodes})


@app.post("/api/synthetic/optimize")
def synthetic_optimize(request: SyntheticRequest) -> dict[str, Any]:
    data = load_synthetic_network(request.nodes)
    objective = Objective(alpha=request.alpha, beta=request.beta)
    runs: dict[str, Any] = {}
    for name in request.algorithms:
        if name == "Exacto":
            runs[name] = brute_force(data, objective)
        elif name == "Búsqueda local":
            runs[name] = local_search(
                data, objective, seed=request.seed, restarts=request.restarts
            )
        elif name == "Kernighan–Lin":
            runs[name] = kernighan_lin(
                data, objective, seed=request.seed, restarts=request.restarts
            )
        elif name == "QAOA":
            runs[name] = qaoa_solve(
                data,
                objective,
                p=request.qaoa_p,
                maxiter=request.qaoa_maxiter,
                shots=request.qaoa_shots,
                seed=request.seed,
                optimizer="COBYLA",
                time_limit=request.qaoa_time_limit,
                max_evaluations=request.qaoa_max_evaluations,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Algoritmo no soportado: {name}")

    # Igual que en la red real, la UI necesita una partición legible por nodo.
    id_map = {str(node["id"]): index for index, node in enumerate(data["nodes"])}
    for run in runs.values():
        run["partition"] = _partition_from_bits(run.get("bits"), id_map)

    return _json_safe(
        {
            "network": data,
            "objective": {"alpha": request.alpha, "beta": request.beta},
            "runs": runs,
            "config": request.model_dump(),
        }
    )


@app.get("/api/sources")
def sources() -> dict[str, Any]:
    processing_path = PROCESSED_DIR / "sein_processing_report.json"
    processing = (
        json.loads(processing_path.read_text(encoding="utf-8"))
        if processing_path.exists()
        else {}
    )
    return _json_safe(
        {
            "source": _source_brief(),
            "quality": _quality_brief(),
            "processing": processing,
            "labels": [
                {
                    "name": "OFICIAL",
                    "tone": "cyan",
                    "description": "Geometrías y atributos descargados de OSINERGMIN.",
                },
                {
                    "name": "DERIVADO",
                    "tone": "blue",
                    "description": "Identidad de estaciones, resolución de extremos, aristas y pesos por longitud.",
                },
                {
                    "name": "VALIDADO",
                    "tone": "green",
                    "description": "Solo con evidencia explícita. COES no se automatizó en esta entrega.",
                },
                {
                    "name": "SIMULADO",
                    "tone": "amber",
                    "description": "Demanda, generación fijada en 0, pesos sintéticos y fallas de escenario.",
                },
            ],
            "pipeline": [
                "ArcGIS REST · MapServer OSINERGMIN",
                "GeoJSON crudo con caché y SHA-256",
                "Normalización de estaciones y líneas",
                "Resolución de extremos explícitos",
                "Grafo verificado y componentes",
                "Subred conectada de 2 a 12 nodos",
                "Instancia y solucionadores clásicos/QAOA",
            ],
            "validation": {
                "rule": "Una línea es arista solo si NODO_SALIDA y NODO_LLEGADA resuelven a dos estaciones.",
                "proximity": "La proximidad solo desempata candidatos con el mismo nombre; no crea conexiones.",
                "coes": "NO_AUTOMATIZADA · ninguna arista se declara validada por COES.",
                "supply": "Una componente conectada no certifica suministro eléctrico.",
            },
            "limitations": [
                "No se modelan flujo AC/DC, frecuencia, protecciones, estabilidad ni energía no suministrada.",
                "La demanda por subestación no está disponible en la fuente; se usa un supuesto SIMULADO.",
                "La generación se fija en 0 porque no hay despacho por subestación.",
                "Las fallas son escenarios topológicos, no órdenes de operación.",
                "Los resultados no demuestran ventaja cuántica ni reducción de riesgo climático.",
            ],
        }
    )


# ---------------------------------------------------------------------------
# Servir el build de React desde el mismo proceso (producción local)
# ---------------------------------------------------------------------------

if DIST_DIR.exists():
    assets = DIST_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
