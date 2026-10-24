"""Geometría y normalización sin dependencias GDAL.

Las operaciones son suficientes para puntos y polilíneas WGS84 del SEIN:
longitudes geodésicas, simplificación, distancias punto-segmento y validación.
Si el entorno dispone de pyproj/Shapely, pueden usarse externamente; este
pipeline no las requiere para ser reproducible.
"""
from __future__ import annotations

from math import asin, cos, isfinite, radians, sin, sqrt
import re
import unicodedata
from typing import Any, Iterable, Iterator, Sequence

EARTH_RADIUS_KM = 6371.0088
Coord = tuple[float, float]


class GeometryError(ValueError):
    pass


def as_coord(value: Sequence[Any]) -> Coord:
    if len(value) < 2:
        raise GeometryError("Coordenada incompleta.")
    lon, lat = float(value[0]), float(value[1])
    if not (isfinite(lon) and isfinite(lat)):
        raise GeometryError("Coordenada no finita.")
    return lon, lat


def valid_coord(lon: float, lat: float) -> bool:
    return isfinite(lon) and isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90


def iter_coords(geometry: dict[str, Any] | None) -> Iterator[Coord]:
    if not geometry:
        return
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Point" and coords:
        yield as_coord(coords)
    elif kind == "LineString" and coords:
        for item in coords:
            yield as_coord(item)
    elif kind == "MultiLineString" and coords:
        for line in coords:
            for item in line:
                yield as_coord(item)
    elif kind == "Polygon" and coords:
        for ring in coords:
            for item in ring:
                yield as_coord(item)
    elif kind == "MultiPolygon" and coords:
        for polygon in coords:
            for ring in polygon:
                for item in ring:
                    yield as_coord(item)


def geometry_lines(geometry: dict[str, Any] | None) -> list[list[Coord]]:
    """Devuelve las polilíneas de una geometría, sin inventar segmentos."""
    if not geometry:
        return []
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "LineString":
        return [[as_coord(item) for item in coords]]
    if kind == "MultiLineString":
        return [[as_coord(item) for item in line] for line in coords]
    return []


def endpoints(geometry: dict[str, Any] | None) -> tuple[Coord | None, Coord | None]:
    lines = geometry_lines(geometry)
    if not lines:
        return None, None
    first = lines[0][0] if lines[0] else None
    last = lines[-1][-1] if lines[-1] else None
    return first, last


def centroid(geometry: dict[str, Any] | None) -> Coord | None:
    coords = list(iter_coords(geometry))
    if not coords:
        return None
    return (
        sum(item[0] for item in coords) / len(coords),
        sum(item[1] for item in coords) / len(coords),
    )


def haversine_km(a: Sequence[float], b: Sequence[float]) -> float:
    lon1, lat1 = radians(float(a[0])), radians(float(a[1]))
    lon2, lat2 = radians(float(b[0])), radians(float(b[1]))
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(min(1.0, sqrt(h)))


def line_length_km(coords: Iterable[Sequence[float]]) -> float:
    points = [as_coord(item) for item in coords]
    return sum(haversine_km(points[i], points[i + 1]) for i in range(len(points) - 1))


def geometry_length_km(geometry: dict[str, Any] | None) -> float:
    return sum(line_length_km(line) for line in geometry_lines(geometry))


def bbox(geometry: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    coords = list(iter_coords(geometry))
    if not coords:
        return None
    lons = [item[0] for item in coords]
    lats = [item[1] for item in coords]
    return min(lons), min(lats), max(lons), max(lats)


def validate_geometry(geometry: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if not geometry or not isinstance(geometry, dict):
        return ["Geometría ausente o no es objeto."]
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind not in {"Point", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}:
        return [f"Tipo de geometría no soportado: {kind}"]
    try:
        points = list(iter_coords(geometry))
    except (GeometryError, TypeError, ValueError) as exc:
        return [f"Coordenada inválida: {exc}"]
    if not points:
        errors.append("Geometría vacía.")
    for lon, lat in points:
        if not valid_coord(lon, lat):
            errors.append(f"Coordenada fuera de rango: ({lon}, {lat}).")
            break
    if kind == "LineString":
        if not coords or len(coords) < 2:
            errors.append("LineString requiere al menos dos puntos.")
        elif len({(float(p[0]), float(p[1])) for p in coords}) < 2:
            errors.append("LineString degenerada.")
    if kind == "MultiLineString":
        if not coords:
            errors.append("MultiLineString vacía.")
        for line in coords or []:
            if len(line) < 2:
                errors.append("Una parte de MultiLineString tiene menos de dos puntos.")
                break
    if kind in {"Polygon", "MultiPolygon"}:
        rings = coords if kind == "Polygon" else [ring for poly in coords for ring in poly]
        for ring in rings or []:
            if len(ring) < 4:
                errors.append("Anillo con menos de cuatro puntos.")
                break
            if tuple(ring[0][:2]) != tuple(ring[-1][:2]):
                errors.append("Anillo no cerrado.")
                break
    return errors


def _point_segment_km(point: Coord, a: Coord, b: Coord) -> float:
    # Proyección equirectangular local: error despreciable a escala de línea.
    lon0, lat0 = point
    scale_x = 111.320 * cos(radians(lat0))
    scale_y = 110.574
    px, py = 0.0, 0.0
    ax, ay = (a[0] - lon0) * scale_x, (a[1] - lat0) * scale_y
    bx, by = (b[0] - lon0) * scale_x, (b[1] - lat0) * scale_y
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return sqrt(ax * ax + ay * ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return sqrt(cx * cx + cy * cy)


def nearest_distance_km(point: Sequence[float], coords: Sequence[Sequence[float]]) -> float:
    pts = [as_coord(item) for item in coords]
    if not pts:
        return float("inf")
    p = as_coord(point)
    if len(pts) == 1:
        return haversine_km(p, pts[0])
    return min(_point_segment_km(p, pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def simplify_line(coords: Sequence[Sequence[float]], tolerance_deg: float = 0.001) -> list[list[float]]:
    """Ramer–Douglas–Peucker en coordenadas geográficas."""
    points = [list(as_coord(item)) for item in coords]
    if len(points) <= 2 or tolerance_deg <= 0:
        return points

    def rdp(seq: list[list[float]]) -> list[list[float]]:
        if len(seq) <= 2:
            return seq
        a, b = seq[0], seq[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        norm = sqrt(dx * dx + dy * dy)
        best, index = -1.0, 0
        for i in range(1, len(seq) - 1):
            if norm == 0:
                dist = sqrt((seq[i][0] - a[0]) ** 2 + (seq[i][1] - a[1]) ** 2)
            else:
                dist = abs(dy * seq[i][0] - dx * seq[i][1] + b[0] * a[1] - b[1] * a[0]) / norm
            if dist > best:
                best, index = dist, i
        if best > tolerance_deg:
            left = rdp(seq[: index + 1])
            right = rdp(seq[index:])
            return left[:-1] + right
        return [a, b]

    return rdp(points)


def simplify_geometry(geometry: dict[str, Any] | None, tolerance_deg: float = 0.001) -> dict[str, Any] | None:
    if not geometry:
        return None
    if geometry.get("type") == "LineString":
        return {"type": "LineString", "coordinates": simplify_line(geometry["coordinates"], tolerance_deg)}
    if geometry.get("type") == "MultiLineString":
        return {
            "type": "MultiLineString",
            "coordinates": [simplify_line(line, tolerance_deg) for line in geometry["coordinates"]],
        }
    return geometry


# --------------------------------------------------------------------- names
MOJIBAKE = {
    "\ufffd": "",
    "Ã¡": "á",
    "Ã©": "é",
    "Ã­": "í",
    "Ã³": "ó",
    "Ãº": "ú",
    "Ã±": "ñ",
    "Â°": "°",
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    for bad, good in MOJIBAKE.items():
        text = text.replace(bad, good)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.upper().replace("&", " Y ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


VOLTAGE_SUFFIX = re.compile(r"\s+(?:22[.,]9|30|33|34[.,]5|44|50|60|66|69|110|138|145|220|500)(?:\s*KV)?$")
PREFIXES = (
    "SUBESTACION ",
    "SUBESTACION",
    "S E ",
    "S E",
    "SE ",
    "SET ",
    "S E M ",
)
POWER_PREFIXES = (
    "CENTRAL HIDROELECTRICA ",
    "CENTRAL TERMICA ",
    "CENTRAL ",
    "C H ",
    "C H",
    "CH ",
    "C T ",
    "C T",
    "CT ",
)


def _strip_prefix(text: str, prefixes: Sequence[str]) -> str:
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if text.startswith(prefix) and len(text) > len(prefix):
                text = text[len(prefix) :].strip()
                changed = True
    return text


def name_variants(value: Any) -> set[str]:
    """Variantes conservadoras para comparar nombres explícitos de extremos."""
    full = normalize_text(value)
    if not full:
        return set()
    variants = {full}
    base = _strip_prefix(full, PREFIXES)
    base = VOLTAGE_SUFFIX.sub("", base).strip()
    variants.add(base)
    power = _strip_prefix(full, POWER_PREFIXES)
    power = VOLTAGE_SUFFIX.sub("", power).strip()
    variants.add(power)
    # "8B" vs "8 B" y nombres con guiones ya quedan normalizados.
    variants.add(re.sub(r"\s+", "", base))
    return {item for item in variants if item}


def clean_name(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    for bad, good in MOJIBAKE.items():
        text = text.replace(bad, good)
    return re.sub(r"\s+", " ", text)


def parse_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def point_in_bbox(point: Sequence[float], box: Sequence[float]) -> bool:
    lon, lat = float(point[0]), float(point[1])
    xmin, ymin, xmax, ymax = [float(v) for v in box]
    return xmin <= lon <= xmax and ymin <= lat <= ymax
