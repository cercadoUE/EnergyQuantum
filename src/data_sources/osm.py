"""OpenStreetMap: fuente complementaria opcional, nunca fusionada en silencio.

No se descarga el PBF nacional automáticamente porque pesa cientos de MB y
requiere herramientas externas. Si el usuario entrega un extracto `.osm` de
Geofabrik/Overpass, este módulo lo convierte a GeoJSON con procedencia separada.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from typing import Any

GEOFABRIK_PERU = "https://download.geofabrik.de/south-america/peru.html"
SOURCE = "OpenStreetMap"
LICENSE = "ODbL-1.0"
POWER_WAYS = {"line", "minor_line", "cable"}
POWER_NODES = {"substation", "plant", "generator", "transformer"}


class OSMError(ValueError):
    pass


def _tags(element: ET.Element) -> dict[str, str]:
    return {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag") if "k" in tag.attrib}


def load_osm_extract(path: str | Path, *, max_elements: int | None = None) -> dict[str, Any]:
    """Convierte un .osm XML en features eléctricas sin inferir conexiones."""
    path = Path(path)
    if not path.exists():
        raise OSMError(f"No existe el extracto OSM: {path}")
    root = ET.parse(path).getroot()
    nodes: dict[str, tuple[float, float]] = {}
    for node in root.findall("node"):
        try:
            nodes[node.attrib["id"]] = (float(node.attrib["lon"]), float(node.attrib["lat"]))
        except (KeyError, ValueError):
            continue

    features: list[dict[str, Any]] = []
    for way in root.findall("way"):
        tags = _tags(way)
        if tags.get("power") not in POWER_WAYS:
            continue
        coords = [nodes[ref.attrib["ref"]] for ref in way.findall("nd") if ref.attrib.get("ref") in nodes]
        if len(coords) < 2:
            continue
        features.append(
            {
                "type": "Feature",
                "id": f"osm/way/{way.attrib.get('id')}",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    **tags,
                    "osm_id": way.attrib.get("id"),
                    "osm_type": "way",
                    "source": SOURCE,
                    "license": LICENSE,
                },
            }
        )
        if max_elements and len(features) >= max_elements:
            break

    for node in root.findall("node"):
        tags = _tags(node)
        if tags.get("power") not in POWER_NODES:
            continue
        coords = nodes.get(node.attrib.get("id", ""))
        if not coords:
            continue
        features.append(
            {
                "type": "Feature",
                "id": f"osm/node/{node.attrib.get('id')}",
                "geometry": {"type": "Point", "coordinates": list(coords)},
                "properties": {
                    **tags,
                    "osm_id": node.attrib.get("id"),
                    "osm_type": "node",
                    "source": SOURCE,
                    "license": LICENSE,
                },
            }
        )
        if max_elements and len(features) >= max_elements:
            break

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": SOURCE,
            "license": LICENSE,
            "origin": str(path),
            "geofabrik_url": GEOFABRIK_PERU,
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "provenance": "COMPLEMENTARIO",
            "note": "No se mezcla con OSINERGMIN; requiere conciliación explícita.",
        },
    }


def save_osm_extract(path: str | Path, out: str | Path, **kwargs: Any) -> Path:
    payload = load_osm_extract(path, **kwargs)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
