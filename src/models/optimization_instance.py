"""Contrato común entre redes reales y los solucionadores existentes.

Los algoritmos clásicos y QAOA siguen recibiendo el diccionario `nodes/edges`
que ya validaba el proyecto. Este adaptador conserva IDs originales en los
metadatos y crea índices densos 0..n-1 para el solver.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from statistics import median
from typing import Any, Iterable

import numpy as np

from .graph_model import validate

WEIGHT_MODES = {
    "length": "A · longitud geográfica (km)",
    "normalized": "B · costo normalizado por mediana",
    "custom": "C · pesos personalizados",
    "synthetic": "D · escenario sintético",
}

DEMAND_MODES = {
    "uniform": "Demanda uniforme abstracta (1 u.s. por nodo)",
    "capacity_proxy": "Proxy por capacidad de transformación (no es demanda)",
    "custom": "Demanda personalizada",
}


class InstanceError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def assign_weights(
    edges: Iterable[dict[str, Any]],
    mode: str = "length",
    *,
    custom: dict[str, float] | None = None,
    seed: int = 7,
) -> tuple[dict[str, float], dict[str, Any]]:
    edge_list = list(edges)
    if mode not in WEIGHT_MODES:
        raise InstanceError(f"Modo de peso no soportado: {mode}")
    lengths = {edge["id"]: max(float(edge.get("length_km") or 0.0), 0.05) for edge in edge_list}

    if mode == "length":
        weights = lengths
        metadata = {
            "mode": mode,
            "label": WEIGHT_MODES[mode],
            "provenance": "DERIVADO",
            "units": "km",
            "formula": "w_ij = max(LONGITUD_km, 0.05)",
            "warning": "La longitud es un indicador geométrico, no un costo económico.",
        }
    elif mode == "normalized":
        med = median(lengths.values()) if lengths else 1.0
        weights = {key: max(value / med, 1e-6) for key, value in lengths.items()}
        metadata = {
            "mode": mode,
            "label": WEIGHT_MODES[mode],
            "provenance": "DERIVADO",
            "units": "adimensional",
            "formula": "w_ij = max(LONGITUD_km, 0.05) / mediana(LONGITUD_km)",
            "median_km": med,
            "warning": "Costo normalizado derivado; no es un costo oficial de operación.",
        }
    elif mode == "custom":
        custom = custom or {}
        missing = [edge["id"] for edge in edge_list if edge["id"] not in custom]
        if missing:
            raise InstanceError(f"Faltan pesos personalizados para {len(missing)} conexiones.")
        weights = {}
        for edge in edge_list:
            value = float(custom[edge["id"]])
            if not math.isfinite(value) or value < 0:
                raise InstanceError("Los pesos personalizados deben ser finitos y no negativos.")
            weights[edge["id"]] = value
        metadata = {
            "mode": mode,
            "label": WEIGHT_MODES[mode],
            "provenance": "PERSONALIZADO",
            "units": "definidas por el usuario",
            "formula": "w_ij = valor introducido",
            "warning": "Pesos definidos por el usuario; no son datos oficiales.",
        }
    else:
        rng = np.random.default_rng(seed)
        ordered = sorted(edge_list, key=lambda edge: edge["id"])
        weights = {edge["id"]: float(rng.uniform(1.0, 10.0)) for edge in ordered}
        metadata = {
            "mode": mode,
            "label": WEIGHT_MODES[mode],
            "provenance": "SIMULADO",
            "units": "adimensional",
            "formula": "w_ij ~ Uniforme(1, 10), semilla fija",
            "seed": seed,
            "warning": "Pesos sintéticos de escenario; no representan costos reales.",
        }
    return weights, metadata


def _demand_values(
    nodes: list[dict[str, Any]],
    mode: str,
    *,
    value: float = 1.0,
    custom: dict[str, float] | None = None,
) -> tuple[dict[str, float], dict[str, Any]]:
    if mode not in DEMAND_MODES:
        raise InstanceError(f"Modo de demanda no soportado: {mode}")
    if mode == "uniform":
        values = {node["id"]: float(value) for node in nodes}
        meta = {
            "mode": mode,
            "label": DEMAND_MODES[mode],
            "provenance": "SIMULADO",
            "formula": f"d_i = {value:g} para todo nodo",
            "warning": "OSINERGMIN no provee demanda por subestación; este valor es un supuesto abstracto.",
        }
    elif mode == "capacity_proxy":
        capacities = [float(node.get("capacity_mva") or 0.0) for node in nodes]
        if max(capacities, default=0) <= 0:
            values = {node["id"]: 1.0 for node in nodes}
        else:
            values = {
                node["id"]: max(float(node.get("capacity_mva") or 0.0), 0.1) for node in nodes
            }
        meta = {
            "mode": mode,
            "label": DEMAND_MODES[mode],
            "provenance": "DERIVADO",
            "formula": "d_i = max(CAPACIDAD_MVA, 0.1); no es demanda",
            "warning": "CAPACIDAD de transformación no es demanda; se usa solo como proxy de escala.",
        }
    else:
        custom = custom or {}
        missing = [node["id"] for node in nodes if node["id"] not in custom]
        if missing:
            raise InstanceError(f"Faltan demandas para {len(missing)} nodos.")
        values = {node["id"]: float(custom[node["id"]]) for node in nodes}
        if any(not math.isfinite(v) or v < 0 for v in values.values()):
            raise InstanceError("Las demandas deben ser finitas y no negativas.")
        meta = {
            "mode": mode,
            "label": DEMAND_MODES[mode],
            "provenance": "PERSONALIZADO",
            "formula": "d_i = valor introducido",
            "warning": "Demandas definidas por el usuario; no son datos oficiales.",
        }
    if sum(values.values()) <= 0:
        raise InstanceError("La demanda total debe ser positiva.")
    return values, meta


@dataclass
class InstanceNode:
    id: str
    name: str
    lon: float
    lat: float
    demand: float
    generation: float
    priority: float
    operational: bool
    voltage_kv: float | None
    department: str | None
    source_id: str
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InstanceEdge:
    id: str
    source: str
    target: str
    weight: float
    length_km: float
    voltage_kv: float | None
    available: bool
    failed: bool
    line_ids: list[str]
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationInstance:
    nodes: list[InstanceNode]
    edges: list[InstanceEdge]
    constraints: dict[str, Any]
    source_metadata: dict[str, Any]
    scenario_metadata: dict[str, Any]
    created_at_utc: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "created_at_utc": self.created_at_utc,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "constraints": self.constraints,
            "source_metadata": self.source_metadata,
            "scenario_metadata": self.scenario_metadata,
        }

    def fingerprint(self) -> str:
        payload = self.to_dict()
        payload.pop("created_at_utc", None)
        return sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
        ).hexdigest()

    def to_solver_data(self) -> dict[str, Any]:
        """Diccionario compatible con Objective, validadores y solucionadores."""
        ordered = sorted(self.nodes, key=lambda node: (node.name, node.id))
        index = {node.id: position for position, node in enumerate(ordered)}
        if len(ordered) < 2:
            raise InstanceError("Se requieren al menos dos nodos.")
        if len(ordered) > 12:
            raise InstanceError("Los solucionadores actuales aceptan como máximo 12 nodos.")
        points = [(node.lon, node.lat) for node in ordered]
        min_lon, max_lon = min(p[0] for p in points), max(p[0] for p in points)
        min_lat, max_lat = min(p[1] for p in points), max(p[1] for p in points)
        span_lon = max(max_lon - min_lon, 1e-9)
        span_lat = max(max_lat - min_lat, 1e-9)
        data_nodes = []
        for node in ordered:
            data_nodes.append(
                {
                    "id": index[node.id],
                    "name": node.name,
                    "demand": float(node.demand),
                    "generation": float(node.generation),
                    "priority": float(node.priority),
                    "type": "Subestación real / escenario",
                    "position": [
                        round((node.lon - min_lon) / span_lon, 6),
                        round((node.lat - min_lat) / span_lat, 6),
                    ],
                    "operational": bool(node.operational),
                    "source_id": node.id,
                    "voltage_kv": node.voltage_kv,
                    "department": node.department,
                }
            )
        data_edges = []
        seen: set[tuple[int, int]] = set()
        for edge in self.edges:
            if edge.source not in index or edge.target not in index:
                raise InstanceError("Una arista referencia un nodo ausente.")
            a, b = index[edge.source], index[edge.target]
            if a == b:
                raise InstanceError("Arista con extremos idénticos.")
            pair = tuple(sorted((a, b)))
            if pair in seen:
                raise InstanceError("Arista duplicada en la instancia.")
            seen.add(pair)
            data_edges.append(
                {
                    "source": a,
                    "target": b,
                    "cost": float(edge.weight),
                    "available": bool(edge.available),
                    "failed": bool(edge.failed),
                    "vulnerability": 0.0,
                    "capacity": 0.0,
                    "source_id": edge.id,
                    "length_km": float(edge.length_km),
                    "voltage_kv": edge.voltage_kv,
                    "line_ids": edge.line_ids,
                    "validation": "verified_endpoint_attributes",
                }
            )
        data = {
            "nodes": data_nodes,
            "edges": data_edges,
            "instance_metadata": {
                "fingerprint": self.fingerprint(),
                "source_metadata": self.source_metadata,
                "scenario_metadata": self.scenario_metadata,
                "constraints": self.constraints,
                "id_map": {node.id: index[node.id] for node in ordered},
            },
        }
        return validate(data)


def build_instance(
    subnet: dict[str, Any] | Any,
    *,
    weight_mode: str = "length",
    demand_mode: str = "uniform",
    demand_value: float = 1.0,
    custom_demands: dict[str, float] | None = None,
    custom_weights: dict[str, float] | None = None,
    seed: int = 7,
    failed_edge_ids: Iterable[str] = (),
    source_metadata: dict[str, Any] | None = None,
) -> OptimizationInstance:
    payload = subnet.to_dict() if hasattr(subnet, "to_dict") else subnet
    node_rows = list(payload.get("nodes", []))
    edge_rows = list(payload.get("edges", []))
    if len(node_rows) < 2:
        raise InstanceError("La subred necesita al menos dos nodos.")
    if len(node_rows) > 12:
        raise InstanceError("La subred excede el máximo de 12 nodos de los solucionadores actuales.")
    if not edge_rows:
        raise InstanceError("La subred no tiene conexiones verificadas.")

    demands, demand_meta = _demand_values(
        node_rows, demand_mode, value=demand_value, custom=custom_demands
    )
    weights, weight_meta = assign_weights(edge_rows, weight_mode, custom=custom_weights, seed=seed)
    failed = set(failed_edge_ids)

    nodes = [
        InstanceNode(
            id=str(node["id"]),
            name=str(node.get("name") or node["id"]),
            lon=float(node["lon"]),
            lat=float(node["lat"]),
            demand=float(demands[node["id"]]),
            generation=0.0,
            priority=1.0,
            operational=bool(node.get("operational")) if node.get("operational") is not None else True,
            voltage_kv=node.get("voltage_kv"),
            department=node.get("department"),
            source_id=str(node["id"]),
            source_metadata={
                "source_ids": node.get("source_ids", []),
                "source_layers": node.get("source_layers", []),
                "provenance": node.get("provenance", "OFICIAL"),
                "identity_provenance": node.get("identity_provenance", "DERIVADO"),
                "operational_assumption": node.get("operational") is None,
            },
        )
        for node in node_rows
    ]
    edges = [
        InstanceEdge(
            id=str(edge["id"]),
            source=str(edge["source"]),
            target=str(edge["target"]),
            weight=float(weights[edge["id"]]),
            length_km=float(edge.get("length_km") or 0.0),
            voltage_kv=edge.get("voltage_kv"),
            available=not (
                str(edge["id"]) in failed or bool(edge.get("failed", False))
            ),
            failed=str(edge["id"]) in failed,
            line_ids=list(edge.get("line_ids", [])),
            source_metadata={
                "validation": edge.get("validation"),
                "coes_validated": False,
                "source": edge.get("data_source", "OSINERGMIN"),
                "line_count": edge.get("line_count", 1),
            },
        )
        for edge in edge_rows
    ]
    if failed:
        # IDs inexistentes no deben pasar silenciosamente.
        missing = sorted(set(failed) - {edge.id for edge in edges})
        if missing:
            raise InstanceError(f"Fallos solicitados inexistentes: {missing}")

    constraints = {
        "base": "dos grupos no vacíos (validación externa)",
        "connectivity": "diagnóstico, no restricción del Hamiltoniano",
        "generation": "no disponible; generación fijada en 0",
        "flow": "no modelado",
        "failed_edges_excluded_from_cut": True,
    }
    scenario = {
        "weight": weight_meta,
        "demand": demand_meta,
        "generation": {
            "mode": "none",
            "value": 0.0,
            "provenance": "NO_DISPONIBLE",
            "warning": "No hay despacho ni generación por subestación en la fuente.",
        },
        "failed_edge_ids": sorted(failed),
        "seed": seed,
        "provenance": "SIMULADO",
        "assumptions": [
            "Las estaciones sin estado operativo explícito se asumen operativas.",
            "La demanda es un supuesto del escenario, no un dato oficial.",
            "La generación se fija en cero; la métrica de suficiencia no es interpretable como operación.",
        ],
    }
    return OptimizationInstance(
        nodes=nodes,
        edges=edges,
        constraints=constraints,
        source_metadata=source_metadata
        or {
            "institution": "OSINERGMIN",
            "provenance": "OFICIAL",
            "derived_topology": "DERIVADO",
            "coes_validation": "NO_AUTOMATIZADA",
        },
        scenario_metadata=scenario,
    )


def apply_failures(instance: OptimizationInstance, edge_ids: Iterable[str]) -> OptimizationInstance:
    failed = set(str(edge_id) for edge_id in edge_ids)
    known = {edge.id for edge in instance.edges}
    missing = sorted(failed - known)
    if missing:
        raise InstanceError(f"Fallos inexistentes: {missing}")
    edges = [
        InstanceEdge(
            id=edge.id,
            source=edge.source,
            target=edge.target,
            weight=edge.weight,
            length_km=edge.length_km,
            voltage_kv=edge.voltage_kv,
            available=edge.available and edge.id not in failed,
            failed=edge.failed or edge.id in failed,
            line_ids=edge.line_ids,
            source_metadata=edge.source_metadata,
        )
        for edge in instance.edges
    ]
    scenario = json.loads(json.dumps(instance.scenario_metadata, ensure_ascii=False))
    scenario["failed_edge_ids"] = sorted(set(scenario.get("failed_edge_ids", [])) | failed)
    return OptimizationInstance(
        nodes=instance.nodes,
        edges=edges,
        constraints=instance.constraints,
        source_metadata=instance.source_metadata,
        scenario_metadata=scenario,
    )
