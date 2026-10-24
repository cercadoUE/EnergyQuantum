"""Pruebas de datos reales, topología, instancias, fallas y exportaciones.

No requieren red: usan snapshots locales y un cliente ArcGIS simulado. La prueba
opcional contra OSINERGMIN se activa con QG_LIVE_OSINERGMIN=1.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import networkx as nx
import pytest
import requests

from src.algorithms.classical import brute_force, kernighan_lin, local_search
from src.algorithms.qaoa_solver import solve
from src.data_sources.arcgis import ArcGISClient, ArcGISError, LayerDownload
from src.data_sources.osinergmin import (
    RAW_DIR,
    SERVICE_URL,
    classify_layer,
    download_sein,
    snapshot_quality,
)
from src.geospatial.geometry import (
    endpoints,
    haversine_km,
    name_variants,
    normalize_text,
    parse_number,
    simplify_line,
    validate_geometry,
)
from src.models.objective import Objective
from src.models.optimization_instance import (
    InstanceError,
    apply_failures,
    assign_weights,
    build_instance,
)
from src.network.graph_builder import NETWORK_DIR, build_network, load_network_snapshot, subnet_graph
from src.network.subnet_selector import (
    SubnetError,
    availability_by_size,
    select_subnet,
)
from src.simulation.real_network_failures import (
    compare_metrics,
    fail_edges,
    network_failure_report,
    subnet_metrics,
)
from src.utils.export import (
    config_json,
    edges_csv,
    graphml,
    nodes_csv,
    provenance_json,
    real_experiment_bundle,
    results_csv,
)

SNAPSHOT = NETWORK_DIR / "sein_network.json"
requires_snapshot = pytest.mark.skipif(
    not SNAPSHOT.exists(), reason="Falta data/processed/sein_network.json"
)


# --------------------------------------------------------------------- ArcGIS
class _Response:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8")
        self.text = self.content.decode("utf-8")


class _FakeSession:
    def __init__(self, features: list[dict], *, fail: bool = False) -> None:
        self.features = features
        self.fail = fail
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict | None = None, timeout: float | None = None):
        self.calls.append((url, dict(params or {})))
        if self.fail:
            raise requests.ConnectionError("red simulada no disponible")
        params = params or {}
        if url.endswith("/MapServer"):
            return _Response(
                {
                    "layers": [
                        {
                            "id": 5,
                            "name": "L.T. 220 kV Prueba",
                            "type": "Feature Layer",
                            "geometryType": "esriGeometryPolyline",
                        }
                    ],
                    "tables": [],
                }
            )
        if url.endswith("/5"):
            return _Response(
                {
                    "name": "L.T. 220 kV Prueba",
                    "objectIdField": "OBJECTID",
                    "maxRecordCount": 2,
                    "geometryType": "esriGeometryPolyline",
                    "fields": [{"name": "OBJECTID"}],
                }
            )
        if url.endswith("/5/query"):
            if params.get("returnCountOnly") == "true":
                return _Response({"count": len(self.features)})
            offset = int(params.get("resultOffset", 0))
            page = int(params.get("resultRecordCount", 1000))
            batch = self.features[offset : offset + page]
            return _Response(
                {
                    "features": batch,
                    "exceededTransferLimit": offset + len(batch) < len(self.features),
                }
            )
        return _Response({"error": {"message": "URL inesperada"}}, status_code=500)


def _point_feature(oid: int, lon: float, lat: float) -> dict:
    return {
        "type": "Feature",
        "id": oid,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"OBJECTID": oid, "NOMBRE": f"SET {oid}"},
    }


def test_arcgis_pagination_and_cache(tmp_path: Path) -> None:
    features = [_point_feature(index, -77 + index / 100, -12.0) for index in range(1, 4)]
    session = _FakeSession(features)
    client = ArcGISClient(
        "https://example.test/MapServer", cache_dir=tmp_path, retries=1, backoff=0
    )
    client.session = session
    download = client.query_layer(5, page_size=2)
    assert download.count == 3
    assert download.pages == 2
    assert [feature["id"] for feature in download.features] == [1, 2, 3]
    offsets = [
        params.get("resultOffset")
        for url, params in session.calls
        if url.endswith("/5/query") and params.get("f") == "geojson"
    ]
    assert offsets == [0, 2]
    assert all(feature["properties"]["OBJECTID"] for feature in download.features)

    # La misma consulta se sirve desde caché aunque la red falle.
    offline = ArcGISClient(
        "https://example.test/MapServer", cache_dir=tmp_path, retries=1, backoff=0
    )
    offline.session = _FakeSession(features, fail=True)
    cached = offline.metadata(5)
    assert cached["name"] == "L.T. 220 kV Prueba"
    assert offline.last_request_used_cache

    forced = ArcGISClient(
        "https://example.test/MapServer", cache_dir=tmp_path, retries=1, backoff=0
    )
    forced.session = _FakeSession(features, fail=True)
    fetched = forced.get_json("5", {"f": "json"}, force=True)
    assert fetched.from_cache and fetched.stale and fetched.warning


def test_arcgis_geometry_conversion_and_errors() -> None:
    client = ArcGISClient("https://example.test/MapServer", cache_dir=None, retries=1)
    assert client.esri_to_geojson_geometry({"x": -77, "y": -12}) == {
        "type": "Point",
        "coordinates": [-77.0, -12.0],
    }
    line = client.esri_to_geojson_geometry({"paths": [[[-77, -12], [-77.1, -12.1]]]})
    assert line["type"] == "LineString"
    multi = client.esri_to_geojson_geometry(
        {"paths": [[[-77, -12], [-77.1, -12.1]], [[-77.2, -12.2], [-77.3, -12.3]]]}
    )
    assert multi["type"] == "MultiLineString"
    with pytest.raises(ArcGISError):
        client.esri_to_geojson_geometry({"curvePaths": []})


def test_layer_classification_never_uses_ids() -> None:
    assert classify_layer("L.T. 220 kV Carhuaquero", "esriGeometryPolyline") == "line"
    assert classify_layer("SUBESTACION TRUJILLO SUR", "esriGeometryPoint") == "substation"
    assert classify_layer("CENTRAL HIDROELECTRICA CANON DEL PATO", "esriGeometryPoint") == "generation"
    assert classify_layer("Gen. Aislada - Municipios", "esriGeometryPoint") is None
    assert classify_layer("ESTRUCTURA SEIN", "esriGeometryPolyline") is None
    assert classify_layer("L.T. 220 kV", "esriGeometryPoint") is None


class _FakeDownloadClient:
    """Cliente mínimo para probar el manifiesto sin tocar la red."""

    def __init__(self) -> None:
        self.root = {
            "layers": [
                {
                    "id": 1,
                    "name": "SUBESTACION 220 kV PRUEBA",
                    "type": "Feature Layer",
                    "geometryType": "esriGeometryPoint",
                },
                {
                    "id": 2,
                    "name": "L.T. 220 kV PRUEBA",
                    "type": "Feature Layer",
                    "geometryType": "esriGeometryPolyline",
                },
                {
                    "id": 3,
                    "name": "Gen. Aislada - Municipios",
                    "type": "Feature Layer",
                    "geometryType": "esriGeometryPoint",
                },
            ],
            "tables": [],
        }

    def metadata(self, layer_id=None, *, force=False):
        if layer_id is None:
            return self.root
        return {"name": f"capa {layer_id}", "fields": [], "objectIdField": "OBJECTID"}

    def flatten_layers(self, metadata=None):
        return list((metadata or self.root)["layers"])

    def feature_layers(self, metadata=None):
        return [
            layer
            for layer in self.flatten_layers(metadata)
            if layer.get("type") == "Feature Layer"
        ]

    def query_layer(self, layer_id, **kwargs):
        features = [
            {
                "type": "Feature",
                "id": 1,
                "geometry": (
                    {"type": "Point", "coordinates": [-77.0, -12.0]}
                    if int(layer_id) == 1
                    else {"type": "LineString", "coordinates": [[-77.0, -12.0], [-77.1, -12.0]]}
                ),
                "properties": {"OBJECTID": 1},
            }
        ]
        return LayerDownload(
            layer_id=int(layer_id),
            name=f"capa {layer_id}",
            geometry_type="",
            features=features,
            metadata={},
            pages=1,
            count=1,
            fetched_at="2026-01-01T00:00:00+00:00",
            from_cache=False,
        )


def test_download_manifest_and_provenance(tmp_path: Path) -> None:
    manifest = download_sein(client=_FakeDownloadClient(), raw_dir=tmp_path)
    assert manifest["institution"] == "OSINERGMIN"
    assert manifest["record_total"] == 2
    assert len(manifest["layers"]) == 2
    assert not manifest["errors"]
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "procedencia.jsonl").exists()
    for entry in manifest["layers"]:
        assert (tmp_path / entry["file"]).exists()
        assert entry["provenance"] == "OFICIAL"
    assert len((tmp_path / "procedencia.jsonl").read_text(encoding="utf-8").splitlines()) == 1


# ------------------------------------------------------------------- geometry
def test_geometry_distances_names_and_validation() -> None:
    assert haversine_km((0, 0), (0, 1)) == pytest.approx(111.19, abs=0.2)
    assert haversine_km((-77.0, -12.0), (-77.0, -12.0)) == pytest.approx(0.0)
    assert normalize_text("Subestación Ñuñoa") == "SUBESTACION NUNOA"
    assert normalize_text("SE SanÃ¡") == "SE SANA"
    assert parse_number("220,5") == 220.5
    assert parse_number("no disponible") is None
    assert "ALFA" in name_variants("S.E. ALFA 220 kV")
    assert "ALFA" in name_variants("SUBESTACION ALFA")

    assert validate_geometry(
        {"type": "LineString", "coordinates": [[-77, -12], [-77, -12]]}
    )
    assert not validate_geometry(
        {"type": "LineString", "coordinates": [[-77, -12], [-77.1, -12.1]]}
    )
    assert len(simplify_line([[0, 0], [0.5, 0.00001], [1, 0]], 0.001)) == 2
    first, last = endpoints(
        {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}
    )
    assert first == (0.0, 0.0) and last == (3.0, 3.0)


# ------------------------------------------------------------------- topology
def _station(node_id: str, name: str, lon: float, lat: float, voltage: float = 220.0) -> dict:
    return {
        "id": node_id,
        "name": name,
        "aliases": [name],
        "lon": lon,
        "lat": lat,
        "voltage_kv": voltage,
        "voltages_kv": [voltage],
        "department": "LA LIBERTAD",
        "capacity_mva": 100.0,
        "source_ids": [f"1:{node_id}"],
        "source_layers": ["SUBESTACION 220 kV"],
        "provenance": "OFICIAL",
        "identity_provenance": "DERIVADO",
    }


def _line(
    source_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    from_name: str | None,
    to_name: str | None,
    voltage: float = 220.0,
    state: str = "ES",
) -> dict:
    return {
        "source_id": source_id,
        "name": source_id,
        "from_name": from_name,
        "to_name": to_name,
        "voltage_kv": voltage,
        "state": state,
        "length_km": haversine_km(start, end),
        "geometry": {"type": "LineString", "coordinates": [list(start), list(end)]},
    }


@pytest.fixture()
def synthetic_processed() -> dict:
    stations = [
        _station("st_a", "SUBESTACION ALFA", -77.00, -12.00),
        _station("st_b", "SUBESTACION BETA", -77.10, -12.00),
        _station("st_c", "SUBESTACION GAMMA", -77.20, -12.00),
        _station("st_d", "SUBESTACION DELTA", -77.30, -12.00),
        _station("st_e", "SUBESTACION EPSILON", -78.00, -12.00),
        _station("st_r1", "SUBESTACION REPETIDA", -77.50, -12.000),
        _station("st_r2", "SUBESTACION REPETIDA", -77.50, -12.002),
    ]
    lines = [
        _line("L-AB", (-77.00, -12.00), (-77.10, -12.00), "SUBESTACION ALFA", "SUBESTACION BETA"),
        _line("L-BC", (-77.10, -12.00), (-77.20, -12.00), "BETA", "GAMMA"),
        _line("L-CD", (-77.20, -12.00), (-77.30, -12.00), "SUBESTACION GAMMA", "SUBESTACION DELTA"),
        # Extremos geométricos junto a D, pero sin nombres: no debe crear arista.
        _line("L-BLANK", (-77.10, -12.00), (-77.30, -12.00), "", ""),
        # Nombre inexistente.
        _line("L-GHOST", (-77.00, -12.00), (-77.10, -12.00), "SUBESTACION FANTASMA", "SUBESTACION BETA"),
        # Dos estaciones homónimas casi equidistantes: ambigua, no se elige por cercanía.
        _line(
            "L-AMBIG",
            (-77.50, -12.001),
            (-77.00, -12.00),
            "SUBESTACION REPETIDA",
            "SUBESTACION ALFA",
        ),
        # Autoenlace explícito (geometría no degenerada, extremos en la misma estación).
        _line("L-SELF", (-77.00, -12.00), (-77.001, -12.00), "SUBESTACION ALFA", "SUBESTACION ALFA"),
    ]
    return {
        "stations": stations,
        "lines": lines,
        "generation": [],
        "report": {"merge_radius_km": 0.75},
    }


def test_topology_uses_only_explicit_endpoints(synthetic_processed: dict) -> None:
    network = build_network(synthetic_processed)
    status = {line["source_id"]: line["connectivity_status"] for line in network["lines"]}
    assert status["L-AB"] == "verified"
    assert status["L-BC"] == "verified"
    assert status["L-CD"] == "verified"
    assert status["L-BLANK"].startswith("unverified_missing")
    assert status["L-GHOST"] == "unverified_not_found"
    assert status["L-AMBIG"] == "unverified_ambiguous"
    assert status["L-SELF"] == "invalid_self_loop"

    pairs = {tuple(sorted((edge["source"], edge["target"]))) for edge in network["edges"]}
    assert pairs == {("st_a", "st_b"), ("st_b", "st_c"), ("st_c", "st_d")}
    assert all(edge["validation"] == "verified_endpoint_attributes" for edge in network["edges"])
    assert all(edge["coes_validated"] is False for edge in network["edges"])
    assert network["quality"]["lines_verified"] == 3
    assert network["quality"]["checks"]["self_loops"] == 0
    assert network["quality"]["checks"]["duplicate_edge_pairs"] == 0
    # Ninguna arista toca a EPSILON ni a las estaciones homónimas.
    touched = {node for pair in pairs for node in pair}
    assert "st_e" not in touched and "st_r1" not in touched and "st_r2" not in touched


def test_resolve_endpoint_proximity_only_disambiguates() -> None:
    from src.network.graph_builder import resolve_endpoint

    stations = {
        "st_r1": {"id": "st_r1", "name": "SUBESTACION REPETIDA", "lon": -77.50, "lat": -12.000, "voltages_kv": [220]},
        "st_r2": {"id": "st_r2", "name": "SUBESTACION REPETIDA", "lon": -77.50, "lat": -12.0135, "voltages_kv": [220]},
    }
    index = {"SUBESTACION REPETIDA": ["st_r1", "st_r2"]}
    near_first = resolve_endpoint(
        "SUBESTACION REPETIDA", 220, (-77.50, -12.0018), index, stations
    )
    assert near_first.status == "resolved" and near_first.node_id == "st_r1"
    assert "proximity" in near_first.method
    ambiguous = resolve_endpoint(
        "SUBESTACION REPETIDA", 220, (-77.50, -12.00675), index, stations
    )
    assert ambiguous.status == "ambiguous"


def test_subnet_selection_preserves_ids_and_rejects_disconnected(synthetic_processed: dict) -> None:
    network = build_network(synthetic_processed)
    subnet = select_subnet(network, component_index=0, max_nodes=3)
    assert subnet.stats["nodes"] == 3 and subnet.stats["edges"] == 2
    assert subnet.selection["truncated"] is True
    assert subnet.selection["pool_nodes"] == 4
    original_ids = {node["id"] for node in network["nodes"]}
    assert {node["id"] for node in subnet.nodes} <= original_ids
    assert all(edge["id"].startswith("ed_") for edge in subnet.edges)

    full = select_subnet(network, component_index=0, max_nodes=4)
    assert full.selection["truncated"] is False
    manual = select_subnet(network, node_ids=["st_a", "st_b"])
    assert manual.selection["requested_nodes"] == ["st_a", "st_b"]
    assert manual.selection["truncated"] is False
    with pytest.raises(SubnetError):
        select_subnet(network, node_ids=["st_a", "st_d"])


def test_instance_weights_provenance_and_failures(synthetic_processed: dict) -> None:
    network = build_network(synthetic_processed)
    subnet = select_subnet(network, component_index=0, max_nodes=4).to_dict()

    first = build_instance(subnet, weight_mode="length")
    second = build_instance(subnet, weight_mode="length")
    assert first.fingerprint() == second.fingerprint()
    assert first.scenario_metadata["weight"]["provenance"] == "DERIVADO"
    assert first.scenario_metadata["demand"]["provenance"] == "SIMULADO"
    data = first.to_solver_data()
    assert [node["id"] for node in data["nodes"]] == list(range(4))
    assert len(data["edges"]) == 3
    original_edge_ids = {edge["id"] for edge in subnet["edges"]}
    assert {edge["source_id"] for edge in data["edges"]} == original_edge_ids
    assert all(edge["cost"] > 0 for edge in data["edges"])

    normalized = build_instance(subnet, weight_mode="normalized")
    assert normalized.scenario_metadata["weight"]["provenance"] == "DERIVADO"
    assert any(abs(edge.weight - 1.0) < 1e-9 for edge in normalized.edges)

    synthetic_a = build_instance(subnet, weight_mode="synthetic", seed=11)
    synthetic_b = build_instance(subnet, weight_mode="synthetic", seed=11)
    synthetic_c = build_instance(subnet, weight_mode="synthetic", seed=12)
    assert synthetic_a.fingerprint() == synthetic_b.fingerprint()
    assert synthetic_a.fingerprint() != synthetic_c.fingerprint()
    assert synthetic_a.scenario_metadata["weight"]["provenance"] == "SIMULADO"

    with pytest.raises(InstanceError):
        build_instance(subnet, weight_mode="custom", custom_weights={})

    failed_id = subnet["edges"][0]["id"]
    failed = build_instance(subnet, failed_edge_ids=[failed_id])
    failed_edge = next(edge for edge in failed.edges if edge.id == failed_id)
    assert failed_edge.failed and not failed_edge.available
    assert failed.scenario_metadata["failed_edge_ids"] == [failed_id]

    applied = apply_failures(first, [failed_id])
    assert next(edge for edge in applied.edges if edge.id == failed_id).failed
    assert applied.fingerprint() != first.fingerprint()
    with pytest.raises(InstanceError):
        apply_failures(first, ["ed_inexistente"])


def test_weight_validation_errors(synthetic_processed: dict) -> None:
    network = build_network(synthetic_processed)
    subnet = select_subnet(network, component_index=0, max_nodes=4).to_dict()
    with pytest.raises(InstanceError):
        assign_weights(subnet["edges"], "modo_invalido")
    custom = {edge["id"]: -1 for edge in subnet["edges"]}
    with pytest.raises(InstanceError):
        assign_weights(subnet["edges"], "custom", custom=custom)


# ------------------------------------------------------------------ snapshot
@requires_snapshot
def test_snapshot_integrity_and_provenance() -> None:
    quality = snapshot_quality(RAW_DIR)
    assert quality["ok"], quality["problems"]
    assert quality["records"] > 0 and quality["layers"] >= 10

    network = load_network_snapshot()
    assert network["source"]["institution"] == "OSINERGMIN"
    assert "loaded_layers" not in network["source"]["source_metadata"]
    assert network["source"]["provenance"]["coes_validation"] == "NO_AUTOMATIZADA"
    assert network["source"]["provenance"]["demand"] == "NO_DISPONIBLE"
    assert network["quality"]["checks"]["coes_validated_edges"] == 0
    assert network["quality"]["checks"]["duplicate_node_ids"] == 0
    assert network["quality"]["checks"]["self_loops"] == 0
    node_ids = {node["id"] for node in network["nodes"]}
    assert len(node_ids) == len(network["nodes"])
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in network["edges"])
    assert all(edge["validation"] == "verified_endpoint_attributes" for edge in network["edges"])
    assert all(not edge["coes_validated"] for edge in network["edges"])
    assert all(float(edge["length_km"]) > 0 for edge in network["edges"])
    assert all(node.get("source_ids") for node in network["nodes"])
    graph = subnet_graph(network, available_only=False)
    assert graph.number_of_edges() == len(network["edges"])
    assert graph.number_of_nodes() == len(network["nodes"])


@requires_snapshot
def test_real_subnet_and_optimization() -> None:
    network = load_network_snapshot()
    availability = availability_by_size(network, (4, 6))
    assert availability[4]["available"] and availability[6]["available"]

    subnet = select_subnet(network, component_index=0, max_nodes=6)
    assert subnet.stats["nodes"] == 6
    assert subnet.stats["components"] == 1
    assert subnet.stats["edges"] >= 5
    network_edge_ids = {edge["id"] for edge in network["edges"]}
    assert all(edge["id"] in network_edge_ids for edge in subnet.edges)
    assert all(edge["validation"] == "verified_endpoint_attributes" for edge in subnet.edges)

    instance = build_instance(subnet.to_dict(), weight_mode="length")
    data = instance.to_solver_data()
    objective = Objective()
    exact = brute_force(data, objective)
    local = local_search(data, objective, seed=7)
    kl = kernighan_lin(data, objective, seed=7)
    assert exact["bits"] is not None and exact["objective"] is not None
    assert local["objective"] >= exact["objective"] - 1e-9
    assert kl["objective"] >= exact["objective"] - 1e-9
    assert (exact["validation"] or {}).get("feasible") is True

    qaoa = solve(
        data,
        objective,
        p=1,
        maxiter=4,
        shots=128,
        seed=7,
        optimizer="COBYLA",
        time_limit=60,
        max_evaluations=20,
    )
    assert qaoa["qubits"] == 6
    assert qaoa["counts"]
    assert qaoa["status"] in {"completed", "budget_exceeded"}
    if qaoa["bits"] is not None:
        assert qaoa["objective"] == pytest.approx(objective.terms(data, qaoa["bits"])["objective"])


@requires_snapshot
def test_real_failures_and_comparison() -> None:
    network = load_network_snapshot()
    subnet = select_subnet(network, component_index=0, max_nodes=6)
    payload = subnet.to_dict()
    before = subnet_metrics(payload, include_failed=False)
    assert before["edges_active"] == len(payload["edges"])
    assert before["components"] == 1

    bridges = subnet.stats["bridges"]
    assert bridges, "La subred de prueba debe contener al menos un puente"
    a, b = bridges[0]
    edge_id = next(
        edge["id"]
        for edge in payload["edges"]
        if {edge["source"], edge["target"]} == {a, b}
    )
    failed = fail_edges(payload, [edge_id])
    failed_edge = next(edge for edge in failed["edges"] if edge["id"] == edge_id)
    assert failed_edge["failed"] and not failed_edge["available"]
    after = subnet_metrics(failed, include_failed=False)
    assert after["edges_failed"] == 1
    assert after["edges_active"] == before["edges_active"] - 1
    assert after["components"] == before["components"] + 1
    assert after["isolated_nodes"] >= 1
    assert after["total_length_km_configured"] == before["total_length_km_configured"]
    assert after["total_length_km_active"] < before["total_length_km_active"]
    assert after["served_demand"] is None and after["lost_demand"] is None

    delta = compare_metrics(before, after)
    assert delta["delta"]["edges_active"] == -1
    assert delta["delta"]["components"] == 1
    with pytest.raises(ValueError):
        fail_edges(payload, ["ed_inexistente"])

    report = network_failure_report(network, [edge_id])
    assert report["failed_edge_ids"] == [edge_id]
    assert report["after"]["edges"] == report["before"]["edges"] - 1
    assert report["after"]["components"] >= report["before"]["components"]


@requires_snapshot
def test_real_exports_are_parseable() -> None:
    network = load_network_snapshot()
    subnet = select_subnet(network, component_index=0, max_nodes=4)
    payload = subnet.to_dict()
    instance = build_instance(payload, weight_mode="length")
    runs = {"Exacto": brute_force(instance.to_solver_data(), Objective())}

    bundle = json.loads(
        real_experiment_bundle(network=network, subnet=payload, instance=instance, runs=runs)
    )
    assert bundle["schema_version"] == 2
    assert bundle["source"]["institution"] == "OSINERGMIN"
    assert bundle["network_summary"]["nodes"] == len(network["nodes"])
    assert bundle["instance"]["nodes"]

    assert nodes_csv(payload["nodes"]).splitlines()[0].startswith("id,name,lon,lat")
    assert edges_csv(payload["edges"]).splitlines()[0].startswith("id,source,target")
    assert "Exacto" in results_csv(runs)
    graph_text = graphml(payload)
    parsed = nx.parse_graphml(graph_text)
    assert parsed.number_of_nodes() == len(payload["nodes"])
    assert parsed.number_of_edges() == len(payload["edges"])
    provenance = json.loads(provenance_json(network=network, subnet=payload))
    assert provenance["source"]["institution"] == "OSINERGMIN"
    config = json.loads(config_json(instance))
    assert config["configuration"]["scenario_metadata"]["weight"]["provenance"] == "DERIVADO"


@requires_snapshot
def test_ui_real_failure_flow() -> None:
    from streamlit.testing.v1 import AppTest

    from src.models.graph_model import ROOT

    app = AppTest.from_file(ROOT / "app.py", default_timeout=120).run()
    app.sidebar.radio[0].set_value("Red real · optimización").run()
    assert not app.exception, [error.value for error in app.exception]

    app.button(key="real-run-classical").click().run()
    assert not app.exception, [error.value for error in app.exception]
    baseline_history = dict(app.session_state["real_history"])
    assert len(baseline_history) == 1
    baseline_fingerprint = next(iter(baseline_history))

    # Elige un puente para garantizar un cambio de componentes.
    subnet_payload = app.session_state["real_subnet"]
    bridges = subnet_payload["stats"]["bridges"]
    assert bridges
    a, b = bridges[0]
    bridge_edge = next(
        edge["id"]
        for edge in subnet_payload["edges"]
        if {edge["source"], edge["target"]} == {a, b}
    )
    option = next(
        label
        for label in app.multiselect(key="real-failure-select").options
        if label.startswith(bridge_edge)
    )
    app.multiselect(key="real-failure-select").set_value([option]).run()
    app.button(key="real-apply-failures").click().run()
    assert not app.exception, [error.value for error in app.exception]
    failed_ids = app.session_state["real_failed_edges"]
    assert len(failed_ids) == 1

    app.button(key="real-run-classical").click().run()
    assert not app.exception, [error.value for error in app.exception]
    history = app.session_state["real_history"]
    assert len(history) == 2
    failed_fingerprint = next(key for key in history if key != baseline_fingerprint)
    assert history[failed_fingerprint]["failed_edge_ids"] == failed_ids
    assert any(box.key == "real-compare-baseline" for box in app.selectbox)

    # La tabla de fallas debe mostrar el cambio topológico.
    failure_table = next(
        frame.value
        for frame in app.dataframe
        if "Indicador" in getattr(frame.value, "columns", [])
    )
    rows = {row["Indicador"]: row for row in failure_table.to_dict("records")}
    assert rows["edges_active"]["Antes"] == rows["edges_active"]["Después"] + 1
    assert rows["components"]["Después"] == rows["components"]["Antes"] + 1

    app.button(key="real-clear-failures").click().run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["real_failed_edges"] == []
    assert app.multiselect(key="real-failure-select").value == []


@requires_snapshot
def test_run_real_experiment_script(tmp_path: Path) -> None:
    from scripts.run_real_experiment import main

    out = tmp_path / "experiment.json"
    assert main(["--nodes", "4", "--skip-qaoa", "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert set(payload["runs"]) == {"Exacto", "Búsqueda local", "Kernighan–Lin"}
    assert payload["subnet"]["stats"]["nodes"] == 4
    assert payload["metadata"]["command"].startswith("python -m scripts.run_real_experiment")
    assert "failure_test" in payload["metadata"]


@pytest.mark.skipif(
    os.environ.get("QG_LIVE_OSINERGMIN") != "1",
    reason="Prueba de red opcional; active QG_LIVE_OSINERGMIN=1",
)
def test_live_osinergmin_service_metadata() -> None:
    client = ArcGISClient(SERVICE_URL, cache_dir=None, timeout=30, retries=1, backoff=0)
    metadata = client.metadata()
    assert client.feature_layers(metadata)
