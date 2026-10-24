"""Normalización reproducible: datos crudos OSINERGMIN -> registros derivados.

No se modifica el archivo crudo. Cada registro conserva IDs de origen, capa y
fecha. Las estaciones duplicadas entre capas se agrupan solo cuando comparten
nombre normalizado y están a menos de 750 m; el resto permanece separado.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha1
import json
from pathlib import Path
import re
from typing import Any, Iterable

from ..models.graph_model import ROOT
from .geometry import (
    clean_name,
    geometry_length_km,
    name_variants,
    normalize_text,
    parse_number,
    validate_geometry,
)

PROCESSED_DIR = ROOT / "data" / "processed"
MERGE_RADIUS_KM = 0.75
LENGTH_RATIO_WARN = 0.5


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", normalize_text(value).lower()).strip("_")
    return text[:36] or "nodo"


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    from .geometry import haversine_km

    return haversine_km(a, b)


def _props(feature: dict[str, Any]) -> dict[str, Any]:
    return dict(feature.get("properties") or {})


def _point(feature: dict[str, Any]) -> tuple[float, float] | None:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Point":
        return None
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return None
    return float(coords[0]), float(coords[1])


@dataclass
class StationRecord:
    source_id: str
    source_layer_id: int
    source_layer_name: str
    source_object_id: Any
    source_name: str
    name: str
    name_key: str
    lon: float
    lat: float
    voltage_kv: float | None
    company: str | None
    department: str | None
    province: str | None
    district: str | None
    capacity_mva: float | None
    transformers: float | None
    state: str | None
    geometry: dict[str, Any]
    source_fields: dict[str, Any]
    geometry_errors: list[str]
    retrieved_at: str | None
    provenance: str = "OFICIAL"
    identity_status: str = "unique"


def normalize_station(feature: dict[str, Any], layer: dict[str, Any], retrieved_at: str | None) -> StationRecord | None:
    point = _point(feature)
    if point is None:
        return None
    props = _props(feature)
    source_id = f"{layer.get('id')}:{props.get('OBJECTID', feature.get('id'))}"
    source_name = clean_name(props.get("NOMBRE"))
    if not source_name:
        return None
    variants = sorted(name_variants(source_name))
    return StationRecord(
        source_id=source_id,
        source_layer_id=int(layer.get("id")),
        source_layer_name=str(layer.get("name")),
        source_object_id=props.get("OBJECTID", feature.get("id")),
        source_name=source_name,
        name=source_name,
        name_key=variants[0] if variants else normalize_text(source_name),
        lon=point[0],
        lat=point[1],
        voltage_kv=parse_number(props.get("TENSION_NOM")),
        company=clean_name(props.get("EMPRESA")) or None,
        department=clean_name(props.get("DEPARTAMENTO")) or None,
        province=clean_name(props.get("PROVINCIA")) or None,
        district=clean_name(props.get("DISTRITO")) or None,
        capacity_mva=parse_number(props.get("CAPACIDAD")),
        transformers=parse_number(props.get("TRANSFORMADORES")),
        state=clean_name(props.get("ESTADO")) or None,
        geometry=feature.get("geometry"),
        source_fields={
            key: props.get(key)
            for key in (
                "OBJECTID",
                "NOMBRE",
                "COD_SE",
                "TENSION_NOM",
                "EMPRESA",
                "DEPARTAMENTO",
                "PROVINCIA",
                "DISTRITO",
                "CAPACIDAD",
                "TRANSFORMADORES",
                "ESTADO",
                "TIPO_SISTEMA",
                "REGION_GEOGRAFICA",
            )
            if key in props
        },
        geometry_errors=validate_geometry(feature.get("geometry")),
        retrieved_at=retrieved_at,
    )


def normalize_line(feature: dict[str, Any], layer: dict[str, Any], retrieved_at: str | None) -> dict[str, Any] | None:
    geometry = feature.get("geometry")
    props = _props(feature)
    source_id = f"{layer.get('id')}:{props.get('OBJECTID', feature.get('id'))}"
    if not geometry or geometry.get("type") not in {"LineString", "MultiLineString"}:
        return None
    errors = validate_geometry(geometry)
    official = parse_number(props.get("LONGITUD"))
    computed = geometry_length_km(geometry)
    if official is not None and official > 0:
        length_km, length_source = official, "LONGITUD_OSINERGMIN"
    else:
        length_km, length_source = computed, "GEOMETRIA_WGS84"
    ratio = (official / computed) if official and computed > 0 else None
    if ratio is not None and (ratio < LENGTH_RATIO_WARN or ratio > 1 / LENGTH_RATIO_WARN):
        errors.append(f"Longitud oficial/geometría difiere: {official:.2f} vs {computed:.2f} km.")
    voltage = parse_number(props.get("TENSION_NOM"))
    names = [clean_name(props.get("NODO_SALIDA")), clean_name(props.get("NODO_LLEGADA"))]
    return {
        "source_id": source_id,
        "source_layer_id": int(layer.get("id")),
        "source_layer_name": str(layer.get("name")),
        "source_object_id": props.get("OBJECTID", feature.get("id")),
        "code": clean_name(props.get("COD_LINEA")) or None,
        "name": clean_name(props.get("NOMBRE")) or clean_name(props.get("COD_LINEA")) or source_id,
        "voltage_kv": voltage,
        "length_km": round(float(length_km), 4) if length_km is not None else None,
        "length_geometry_km": round(float(computed), 4),
        "length_official_km": official,
        "length_source": length_source,
        "from_name": names[0] or None,
        "to_name": names[1] or None,
        "geometry": geometry,
        "state": clean_name(props.get("ESTADO")) or None,
        "company": clean_name(props.get("EMPRESA")) or None,
        "area_sein": clean_name(props.get("AREA_SEIN")) or None,
        "system": clean_name(props.get("SISTEMA")) or None,
        "circuit_type": clean_name(props.get("TIPO_CIRCUITO")) or None,
        "conductor": clean_name(props.get("MAT_CODUC")) or None,
        "source_fields": {
            key: props.get(key)
            for key in (
                "OBJECTID",
                "COD_LINEA",
                "NOMBRE",
                "TENSION_NOM",
                "LONGITUD",
                "EMPRESA",
                "ESTADO",
                "NODO_SALIDA",
                "NODO_LLEGADA",
                "AREA_SEIN",
                "SISTEMA",
                "TIPO_CIRCUITO",
                "MAT_CODUC",
            )
            if key in props
        },
        "geometry_errors": errors,
        "retrieved_at": retrieved_at,
        "provenance": "OFICIAL",
        "connectivity_status": "unverified",
        "resolution": None,
        "source_ids": [source_id],
    }


def normalize_generation(feature: dict[str, Any], layer: dict[str, Any], retrieved_at: str | None) -> dict[str, Any] | None:
    point = _point(feature)
    if point is None:
        return None
    props = _props(feature)
    source_id = f"{layer.get('id')}:{props.get('OBJECTID', feature.get('id'))}"
    name = clean_name(props.get("NOMBRE"))
    if not name:
        return None
    return {
        "source_id": source_id,
        "source_layer_id": int(layer.get("id")),
        "source_layer_name": str(layer.get("name")),
        "source_object_id": props.get("OBJECTID", feature.get("id")),
        "name": name,
        "name_key": sorted(name_variants(name))[0],
        "lon": point[0],
        "lat": point[1],
        "voltage_kv": parse_number(props.get("TENSION_NOM")),
        "capacity_installed_mw": parse_number(props.get("POT_INST")),
        "capacity_effective_mw": parse_number(props.get("POT_EFEC")),
        "technology": clean_name(props.get("TIPO_CENTRAL")) or clean_name(layer.get("name")),
        "company": clean_name(props.get("EMPRESA")) or None,
        "department": clean_name(props.get("DEPARTAMENTO")) or None,
        "province": clean_name(props.get("PROVINCIA")) or None,
        "district": clean_name(props.get("DISTRITO")) or None,
        "state": clean_name(props.get("ESTADO")) or None,
        "geometry": feature.get("geometry"),
        "source_fields": {
            key: props.get(key)
            for key in (
                "OBJECTID",
                "NOMBRE",
                "TIPO_CENTRAL",
                "TENSION_NOM",
                "POT_INST",
                "POT_EFEC",
                "EMPRESA",
                "DEPARTAMENTO",
                "PROVINCIA",
                "DISTRITO",
                "ESTADO",
                "TIPO_SISTEMA",
                "FUENTE_ENER",
            )
            if key in props
        },
        "geometry_errors": validate_geometry(feature.get("geometry")),
        "retrieved_at": retrieved_at,
        "provenance": "OFICIAL",
    }


def _isin_sein(props: dict[str, Any]) -> bool:
    system = str(props.get("TIPO_SISTEMA") or props.get("SISTEMA") or "").strip().upper()
    return system in {"", "I", "NAN", "NONE"} or system == "INTERCONECTADO"


def merge_stations(records: Iterable[StationRecord], radius_km: float = MERGE_RADIUS_KM) -> list[dict[str, Any]]:
    """Agrupa representaciones duplicadas por nombre exacto y cercanía."""
    ordered = sorted(records, key=lambda r: (r.name_key, r.lat, r.lon, r.source_layer_id))
    groups: list[list[StationRecord]] = []
    for record in ordered:
        placed = False
        for group in groups:
            head = group[0]
            if head.name_key != record.name_key:
                continue
            if _haversine((head.lon, head.lat), (record.lon, record.lat)) <= radius_km:
                group.append(record)
                placed = True
                break
        if not placed:
            groups.append([record])

    merged: list[dict[str, Any]] = []
    for group in groups:
        primary = max(group, key=lambda r: (r.voltage_kv or 0, len(r.name), r.source_layer_id))
        first_id = group[0].source_id
        digest = sha1(f"{primary.name_key}|{primary.lat:.4f}|{primary.lon:.4f}".encode()).hexdigest()[:8]
        node_id = f"st_{_slug(primary.name)}_{digest}"
        voltages = sorted({r.voltage_kv for r in group if r.voltage_kv is not None})
        capacities = [r.capacity_mva for r in group if r.capacity_mva is not None and r.capacity_mva > 0]
        departments = sorted({r.department for r in group if r.department})
        companies = sorted({r.company for r in group if r.company})
        aliases = sorted({r.source_name for r in group})
        merged.append(
            {
                "id": node_id,
                "name": primary.name,
                "aliases": aliases,
                "name_key": primary.name_key,
                "lon": primary.lon,
                "lat": primary.lat,
                "voltage_kv": max(voltages) if voltages else None,
                "voltages_kv": voltages,
                "department": primary.department or (departments[0] if departments else None),
                "province": primary.province,
                "district": primary.district,
                "company": primary.company or (companies[0] if companies else None),
                "capacity_mva": max(capacities) if capacities else None,
                "transformers": max(
                    [r.transformers for r in group if r.transformers is not None] or [0]
                )
                or None,
                "state": primary.state,
                "operational": None if primary.state is None else primary.state.upper() == "ES",
                "node_type": "substation",
                "geometry": {"type": "Point", "coordinates": [primary.lon, primary.lat]},
                "source_ids": sorted({r.source_id for r in group}),
                "source_layers": sorted({r.source_layer_name for r in group}),
                "source_object_ids": sorted({str(r.source_object_id) for r in group}),
                "source_fields": group[0].source_fields,
                "retrieved_at": primary.retrieved_at,
                "provenance": "OFICIAL",
                "identity_status": "merged_duplicate" if len(group) > 1 else "unique",
                "merge_count": len(group),
                "validation": "valid" if not group[0].geometry_errors else "geometry_warning",
                "first_source_id": first_id,
            }
        )
    merged.sort(key=lambda item: (item["department"] or "", item["name"], item["id"]))
    return merged


def _dedupe_lines(lines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    for line in lines:
        key = (
            normalize_text(line.get("code") or ""),
            normalize_text(line.get("name") or ""),
            round(float(line.get("voltage_kv") or 0), 2),
            normalize_text(line.get("from_name") or ""),
            normalize_text(line.get("to_name") or ""),
        )
        if key[0] and key in index:
            original = index[key]
            if abs(float(original.get("length_km") or 0) - float(line.get("length_km") or 0)) <= max(
                0.05, 0.01 * float(original.get("length_km") or 1)
            ):
                original["source_ids"].append(line["source_id"])
                duplicates.append(
                    {
                        "removed_source_id": line["source_id"],
                        "kept_source_id": original["source_id"],
                        "reason": "mismo código, nombre, tensión y extremos",
                    }
                )
                continue
        index[key] = line
        kept.append(line)
    return kept, duplicates


def process_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Convierte un snapshot cargado en estaciones, líneas y generación."""
    layers = snapshot.get("loaded_layers", {})
    if not layers:
        raise ValueError("El snapshot no contiene capas cargadas.")
    stations: list[StationRecord] = []
    lines: list[dict[str, Any]] = []
    generation: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for layer_id, payload in sorted(layers.items()):
        entry = payload["entry"]
        role = entry.get("role")
        retrieved = entry.get("downloaded_at_utc")
        layer = {
            "id": layer_id,
            "name": entry.get("layer_name"),
        }
        for feature in payload.get("features", []):
            props = _props(feature)
            if not _isin_sein(props):
                skipped.append(
                    {
                        "source_id": f"{layer_id}:{props.get('OBJECTID', feature.get('id'))}",
                        "layer_id": layer_id,
                        "reason": "TIPO_SISTEMA/SISTEMA fuera del SEIN",
                        "system": props.get("TIPO_SISTEMA") or props.get("SISTEMA"),
                    }
                )
                continue
            if role == "substation":
                record = normalize_station(feature, layer, retrieved)
                if record:
                    stations.append(record)
                else:
                    skipped.append({"source_id": f"{layer_id}:{feature.get('id')}", "reason": "geometría o nombre inválido"})
            elif role == "line":
                record = normalize_line(feature, layer, retrieved)
                if record:
                    lines.append(record)
                else:
                    skipped.append({"source_id": f"{layer_id}:{feature.get('id')}", "reason": "geometría de línea inválida"})
            elif role == "generation":
                record = normalize_generation(feature, layer, retrieved)
                if record:
                    generation.append(record)

    merged = merge_stations(stations)
    lines, duplicates = _dedupe_lines(lines)
    return {
        "stations": merged,
        "lines": lines,
        "generation": generation,
        "report": {
            "generated_at_utc": utc_now(),
            "stations_raw": len(stations),
            "stations_merged": len(merged),
            "station_duplicates_merged": sum(max(0, item["merge_count"] - 1) for item in merged),
            "lines_raw": len(lines) + len(duplicates),
            "lines_processed": len(lines),
            "line_duplicates_removed": duplicates,
            "generation_records": len(generation),
            "skipped": skipped,
            "merge_radius_km": MERGE_RADIUS_KM,
            "transformations": [
                "Normalización Unicode/ASCII de nombres y campos.",
                "Tensión numérica desde TENSION_NOM; geometría WGS84 desde outSR=4326.",
                "Longitud oficial LONGITUD cuando es positiva; si no, longitud geodésica.",
                "Estaciones con igual nombre normalizado y ≤0.75 km agrupadas; capacidad = máximo, no suma.",
                "Duplicados de línea con mismo código/nombre/tensión/extremos y longitud similar agrupados.",
                "Registros con TIPO_SISTEMA/SISTEMA 'A' excluidos del SEIN.",
            ],
            "limitations": [
                "La agrupación de estaciones es una identidad derivada, no un activo oficial.",
                "No se dispone de demanda ni de estado operativo para la mayoría de estaciones.",
                "Los extremos de línea se validan después, contra nombres explícitos.",
            ],
        },
    }


def save_processed(result: dict[str, Any], out_dir: str | Path = PROCESSED_DIR) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for key in ("stations", "lines", "generation"):
        path = out_dir / f"sein_{key}.json"
        path.write_text(json.dumps(result[key], ensure_ascii=False, indent=2), encoding="utf-8")
        paths[key] = path
    report_path = out_dir / "sein_processing_report.json"
    report_path.write_text(json.dumps(result["report"], ensure_ascii=False, indent=2), encoding="utf-8")
    paths["report"] = report_path
    return paths


def load_processed(out_dir: str | Path = PROCESSED_DIR) -> dict[str, Any]:
    out_dir = Path(out_dir)
    paths = {key: out_dir / f"sein_{key}.json" for key in ("stations", "lines", "generation")}
    if not all(path.exists() for path in paths.values()):
        raise FileNotFoundError(
            "Faltan datos procesados. Ejecute: python -m scripts.download_sein && "
            "python -m scripts.build_network"
        )
    result = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()}
    report = out_dir / "sein_processing_report.json"
    result["report"] = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    return result
