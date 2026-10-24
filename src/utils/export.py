"""Exportaciones del proyecto. Los contratos sintéticos existentes se conservan."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
import json
from typing import Any, Iterable

import networkx as nx

from ..experiments.reproducibility import environment


def _json_default(value: Any) -> Any:
    if isinstance(value, (set, tuple)):
        return list(value)
    raise TypeError(f"No serializable: {type(value).__name__}")


def _dump(payload: Any, *, indent: int | None = 2) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=indent,
        allow_nan=False,
        default=_json_default,
    )


def bundle(data, objective, runs):
    return json.dumps(
        dict(
            schema_version=1,
            environment=environment(),
            network=data,
            objective=objective.__dict__,
            runs=runs,
        ),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )


# --------------------------------------------------------------------- real
def real_experiment_bundle(
    *,
    network: dict[str, Any] | None,
    subnet: dict[str, Any] | None,
    instance: Any | None,
    runs: dict[str, Any] | None,
    extra: dict[str, Any] | None = None,
) -> str:
    instance_payload = instance.to_dict() if hasattr(instance, "to_dict") else instance
    return _dump(
        {
            "schema_version": 2,
            "exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "environment": environment(),
            "source": network.get("source") if network else None,
            "network_summary": {
                "nodes": len(network.get("nodes", [])) if network else 0,
                "edges": len(network.get("edges", [])) if network else 0,
                "quality": network.get("quality") if network else None,
            },
            "subnet": subnet,
            "instance": instance_payload,
            "runs": runs or {},
            "metadata": extra or {},
        }
    )


def nodes_csv(nodes: Iterable[dict[str, Any]]) -> str:
    rows = list(nodes)
    fields = [
        "id",
        "name",
        "lon",
        "lat",
        "voltage_kv",
        "voltages_kv",
        "department",
        "province",
        "district",
        "company",
        "capacity_mva",
        "state",
        "operational",
        "source_ids",
        "source_layers",
        "provenance",
        "identity_status",
        "component",
    ]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        item = dict(row)
        for key in ("voltages_kv", "source_ids", "source_layers"):
            if isinstance(item.get(key), (list, tuple, set)):
                item[key] = json.dumps(list(item[key]), ensure_ascii=False)
        writer.writerow(item)
    return buffer.getvalue()


def edges_csv(edges: Iterable[dict[str, Any]]) -> str:
    rows = list(edges)
    fields = [
        "id",
        "source",
        "target",
        "source_name",
        "target_name",
        "length_km",
        "voltage_kv",
        "voltages_kv",
        "line_ids",
        "line_count",
        "available",
        "failed",
        "validation",
        "coes_validated",
        "provenance",
    ]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        item = dict(row)
        for key in ("voltages_kv", "line_ids"):
            if isinstance(item.get(key), (list, tuple, set)):
                item[key] = json.dumps(list(item[key]), ensure_ascii=False)
        writer.writerow(item)
    return buffer.getvalue()


def results_csv(runs: dict[str, Any]) -> str:
    fields = [
        "method",
        "objective",
        "cut",
        "seconds",
        "evaluations",
        "seed",
        "status",
        "feasible",
        "feasible_fraction",
        "expected",
        "qubits",
    ]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for name, run in (runs or {}).items():
        row = dict(run)
        row.setdefault("method", name)
        validation = row.get("validation") or {}
        row["feasible"] = validation.get("feasible")
        writer.writerow(row)
    return buffer.getvalue()


def graphml(payload: dict[str, Any], *, name: str = "subnet") -> str:
    """GraphML de una subred, serializando atributos complejos como JSON."""
    graph = nx.Graph()
    for node in payload.get("nodes", []):
        attrs = {}
        for key, value in node.items():
            if isinstance(value, (list, tuple, set, dict)):
                attrs[key] = json.dumps(list(value) if isinstance(value, set) else value, ensure_ascii=False)
            elif value is None:
                attrs[key] = ""
            else:
                attrs[key] = value
        graph.add_node(str(node["id"]), **attrs)
    for edge in payload.get("edges", []):
        attrs = {}
        for key, value in edge.items():
            if key in {"source", "target"}:
                continue
            if isinstance(value, (list, tuple, set, dict)):
                attrs[key] = json.dumps(list(value) if isinstance(value, set) else value, ensure_ascii=False)
            elif value is None:
                attrs[key] = ""
            else:
                attrs[key] = value
        graph.add_edge(str(edge["source"]), str(edge["target"]), **attrs)
    buffer = BytesIO()
    nx.write_graphml(graph, buffer, encoding="utf-8")
    return buffer.getvalue().decode("utf-8")


def provenance_json(
    *,
    network: dict[str, Any] | None,
    subnet: dict[str, Any] | None,
    extra: dict[str, Any] | None = None,
) -> str:
    return _dump(
        {
            "exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": network.get("source") if network else None,
            "network_metadata": network.get("metadata") if network else None,
            "quality": network.get("quality") if network else None,
            "subnet_selection": subnet.get("selection") if subnet else None,
            "subnet_stats": subnet.get("stats") if subnet else None,
            "extra": extra or {},
        }
    )


def config_json(instance: Any, extra: dict[str, Any] | None = None) -> str:
    payload = instance.to_dict() if hasattr(instance, "to_dict") else instance
    return _dump({"configuration": payload, "extra": extra or {}})
