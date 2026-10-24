"""Fuente OSINERGMIN: descubrimiento y descarga del Mapa del SEIN.

Los IDs de capa se descubren desde el metadato del servicio; no se codifican
como verdad permanente. Cada ejecución deja un manifiesto y un registro de
procedencia. Los archivos crudos son inmutables: el procesamiento nunca los
sobrescribe.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable

from ..models.graph_model import ROOT
from .arcgis import ArcGISClient, ArcGISError, LayerDownload, write_json_atomic

SERVICE_URL = (
    "https://gisem.osinergmin.gob.pe/serverosih/rest/services/"
    "Electricidad/MapaSEIN_Operacion/MapServer"
)
RAW_DIR = ROOT / "data" / "raw" / "osinergmin"
PROVENANCE = "procedencia"
OFFICIAL_LABEL = "OFICIAL"
SOURCE_INSTITUTION = "OSINERGMIN"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ascii_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .replace("\ufffd", "")
    )


def slug(value: str, limit: int = 40) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", ascii_text(value).lower()).strip("_")
    return text[:limit] or "capa"


@dataclass(frozen=True)
class TargetLayer:
    role: str
    layer_id: int
    name: str
    geometry_type: str
    voltage_kv: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_voltage(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*kv", str(text), flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def classify_layer(name: str, geometry_type: str | None, parent_name: str = "") -> str | None:
    """Clasifica por nombre, grupo padre y geometría; nunca por ID."""
    text = ascii_text(f"{name} {parent_name}").upper()
    geometry = geometry_type or ""
    # "Gen. Aislada - Municipios" y "C.H./C.T. Aislados" no pertenecen al SEIN.
    if "AISLAD" in text:
        return None
    if "ESTRUCTURA" in text:
        return None
    if "L.T." in text or "LINEA DE TRANSMISION" in text or "LÍNEA DE TRANSMISIÓN" in text:
        return "line" if "Polyline" in geometry else None
    if "SET " in text or "SUBESTACION" in text or "SUBESTACIÓN" in text:
        return "substation" if "Point" in geometry else None
    if any(
        token in text
        for token in (
            "C.H.",
            "C.T.",
            "CENTRAL",
            "HIDROELECTRICA",
            "HIDROELÉCTRICA",
            "TERMICA",
            "TÉRMICA",
            "EOLICA",
            "EÓLICA",
            "SOLAR",
            "BIOMASA",
        )
    ):
        return "generation" if "Point" in geometry else None
    return None


def discover_targets(client: ArcGISClient, *, force: bool = False) -> tuple[dict[str, Any], list[TargetLayer]]:
    metadata = client.metadata(force=force)
    all_layers = client.flatten_layers(metadata)
    names = {layer.get("id"): str(layer.get("name") or "") for layer in all_layers}
    targets: list[TargetLayer] = []
    for layer in client.feature_layers(metadata):
        name = str(layer.get("name") or "")
        parent_name = names.get(layer.get("parentLayerId"), "")
        role = classify_layer(name, layer.get("geometryType"), parent_name)
        if role is None:
            continue
        targets.append(
            TargetLayer(
                role=role,
                layer_id=int(layer["id"]),
                name=name,
                geometry_type=str(layer.get("geometryType") or ""),
                voltage_kv=parse_voltage(name) if role in {"line", "substation"} else None,
            )
        )
    # Orden estable por rol y tensión, no por ID.
    order = {"substation": 0, "line": 1, "generation": 2}
    targets.sort(key=lambda t: (order[t.role], t.voltage_kv or 0.0, t.name))
    return metadata, targets


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_sein(
    *,
    client: ArcGISClient | None = None,
    raw_dir: str | Path = RAW_DIR,
    force: bool = False,
    page_size: int = 1000,
    max_features: int | None = None,
    types: Iterable[str] = ("substation", "line", "generation"),
) -> dict[str, Any]:
    """Descarga capas seleccionadas y actualiza manifiesto/procedencia.

    Si una capa falla y existe una copia previa, se conserva la copia y se
    registra el error. No se inventan datos para completar una capa.
    """
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    client = client or ArcGISClient(SERVICE_URL)
    metadata, targets = discover_targets(client, force=force)
    wanted = set(types)
    targets = [target for target in targets if target.role in wanted]
    if not targets:
        raise ArcGISError("El servicio no expuso capas reconocibles de subestaciones, líneas o generación.")

    service_path = raw_dir / "service_metadata.json"
    write_json_atomic(service_path, metadata)

    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for target in targets:
        filename = f"layer_{target.layer_id:02d}_{slug(target.name)}.geojson"
        path = raw_dir / filename
        layer_meta_path = raw_dir / f"layer_{target.layer_id:02d}_metadata.json"
        try:
            layer_meta = client.metadata(target.layer_id, force=force)
            write_json_atomic(layer_meta_path, layer_meta)
            download = client.query_layer(
                target.layer_id,
                page_size=page_size,
                max_features=max_features,
                force=force,
            )
            write_json_atomic(path, download.feature_collection)
            entry = {
                "layer_id": target.layer_id,
                "layer_name": target.name,
                "role": target.role,
                "voltage_kv_from_name": target.voltage_kv,
                "geometry_type": target.geometry_type,
                "file": filename,
                "file_sha256": _sha256_file(path),
                "records": len(download.features),
                "count_reported": download.count,
                "pages": download.pages,
                "fields": [field.get("name") for field in layer_meta.get("fields", [])],
                "object_id_field": layer_meta.get("objectIdField"),
                "spatial_reference": layer_meta.get("extent", {}).get("spatialReference")
                or layer_meta.get("spatialReference"),
                "downloaded_at_utc": download.fetched_at,
                "from_cache": download.from_cache,
                "warnings": download.warnings,
                "source": SOURCE_INSTITUTION,
                "provenance": OFFICIAL_LABEL,
            }
            entries.append(entry)
        except (ArcGISError, OSError, ValueError) as exc:
            previous = None
            if path.exists():
                previous = {
                    "file": filename,
                    "records": len(json.loads(path.read_text(encoding="utf-8")).get("features", [])),
                    "file_sha256": _sha256_file(path),
                }
            errors.append(
                {
                    "layer_id": str(target.layer_id),
                    "layer_name": target.name,
                    "error": str(exc),
                    "kept_previous": json.dumps(previous, ensure_ascii=False) if previous else "no",
                }
            )

    manifest = {
        "schema_version": 2,
        "institution": SOURCE_INSTITUTION,
        "service": SERVICE_URL,
        "service_metadata_file": "service_metadata.json",
        "downloaded_at_utc": utc_now(),
        "provenance": OFFICIAL_LABEL,
        "classification_note": "OFICIAL identifica la descarga de OSINERGMIN; el procesamiento posterior es DERIVADO.",
        "targets": [target.to_dict() for target in targets],
        "layers": entries,
        "errors": errors,
        "record_total": sum(entry["records"] for entry in entries),
    }
    write_json_atomic(raw_dir / "manifest.json", manifest)

    # Registro append-only: cada descarga conserva su fecha y errores.
    with (raw_dir / f"{PROVENANCE}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False) + "\n")

    return manifest


def load_snapshot(raw_dir: str | Path = RAW_DIR) -> dict[str, Any]:
    """Carga la última copia local sin tocar la red."""
    raw_dir = Path(raw_dir)
    manifest_path = raw_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"No existe {manifest_path}. Ejecute: python -m scripts.download_sein"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    layers: dict[int, dict[str, Any]] = {}
    for entry in manifest.get("layers", []):
        path = raw_dir / entry["file"]
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        layers[int(entry["layer_id"])] = {
            "entry": entry,
            "features": payload.get("features", []),
        }
    manifest["loaded_layers"] = layers
    return manifest


def snapshot_quality(raw_dir: str | Path = RAW_DIR) -> dict[str, Any]:
    """Comprueba integridad del snapshot sin red (hash, conteos, geometrías)."""
    manifest = load_snapshot(raw_dir)
    problems: list[str] = []
    for layer_id, payload in manifest["loaded_layers"].items():
        entry = payload["entry"]
        path = Path(raw_dir) / entry["file"]
        if _sha256_file(path) != entry["file_sha256"]:
            problems.append(f"Hash distinto en capa {layer_id}")
        if len(payload["features"]) != entry["records"]:
            problems.append(f"Conteo distinto en capa {layer_id}")
        if not payload["features"]:
            problems.append(f"Capa vacía: {layer_id}")
        for feature in payload["features"][:5]:
            if not feature.get("geometry"):
                problems.append(f"Geometría ausente en capa {layer_id}")
                break
    return {
        "ok": not problems and bool(manifest["loaded_layers"]),
        "problems": problems,
        "layers": len(manifest["loaded_layers"]),
        "records": sum(len(p["features"]) for p in manifest["loaded_layers"].values()),
    }
