"""Cliente mínimo y auditable para servicios ArcGIS REST.

El módulo no depende de GDAL/GeoPandas. Descarga GeoJSON cuando el servicio lo
admite y, si no, convierte geometrías Esri JSON. Toda respuesta queda cacheada
con URL, parámetros, fecha y hash para poder repetir el análisis sin red.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any, Iterable

import requests

from ..models.graph_model import ROOT

DEFAULT_CACHE = ROOT / "data" / "cache" / "arcgis"
USER_AGENT = "EnergyQuantumPeru/2.0 (research; OSINERGMIN-ArcGIS)"


class ArcGISError(RuntimeError):
    """Error de servicio, paginación o formato ArcGIS."""


@dataclass
class Fetched:
    payload: dict[str, Any]
    url: str
    params: dict[str, Any]
    fetched_at: str
    from_cache: bool = False
    stale: bool = False
    warning: str | None = None


@dataclass
class LayerDownload:
    layer_id: int
    name: str
    geometry_type: str | None
    features: list[dict[str, Any]]
    metadata: dict[str, Any]
    pages: int
    count: int | None
    fetched_at: str
    from_cache: bool
    warnings: list[str] = field(default_factory=list)

    @property
    def feature_collection(self) -> dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "features": self.features,
            "properties": {
                "layer_id": self.layer_id,
                "layer_name": self.name,
                "geometry_type": self.geometry_type,
            },
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ArcGISClient:
    """Cliente REST con reintentos limitados, caché local y modo offline."""

    def __init__(
        self,
        base_url: str,
        cache_dir: str | Path | None = DEFAULT_CACHE,
        timeout: float = 45.0,
        retries: int = 3,
        backoff: float = 1.5,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout = timeout
        self.retries = max(1, int(retries))
        self.backoff = backoff
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.last_request_used_cache = False
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ HTTP
    def _cache_path(self, url: str, params: dict[str, Any]) -> Path | None:
        if not self.cache_dir:
            return None
        digest = sha256((url + "?" + _stable_json(params)).encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, path: Path | None) -> dict[str, Any] | None:
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _write_cache(self, path: Path | None, record: dict[str, Any]) -> None:
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)

    def get_json(
        self,
        path: str = "",
        params: dict[str, Any] | None = None,
        *,
        force: bool = False,
        allow_stale: bool = True,
    ) -> Fetched:
        """GET JSON con reintentos; si la red falla usa la última copia local."""
        params = dict(params or {})
        url = f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url
        cache_path = self._cache_path(url, params)
        cached = self._read_cache(cache_path)
        if cached and not force:
            self.last_request_used_cache = True
            return Fetched(
                payload=cached["payload"],
                url=url,
                params=params,
                fetched_at=cached.get("fetched_at", ""),
                from_cache=True,
                stale=True,
                warning="Respuesta servida desde caché local.",
            )

        error: str | None = None
        for attempt in range(self.retries):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise ArcGISError(f"HTTP {response.status_code}")
                if response.status_code >= 400:
                    raise ArcGISError(f"HTTP {response.status_code}: {response.text[:300]}")
                # ArcGIS a veces declara UTF-8 pero envía mojibake; nunca usamos
                # response.json() para evitar decodificaciones dependientes del host.
                payload = json.loads(response.content.decode("utf-8", errors="replace"))
                if isinstance(payload, dict) and payload.get("error"):
                    raise ArcGISError(str(payload["error"]))
                record = {"url": url, "params": params, "fetched_at": utc_now(), "payload": payload}
                self._write_cache(cache_path, record)
                self.last_request_used_cache = False
                return Fetched(payload, url, params, record["fetched_at"])
            except (requests.RequestException, ArcGISError, ValueError) as exc:
                error = str(exc)
                if attempt + 1 < self.retries and self.backoff:
                    time.sleep(self.backoff * (2**attempt))

        if cached and allow_stale:
            self.last_request_used_cache = True
            return Fetched(
                payload=cached["payload"],
                url=url,
                params=params,
                fetched_at=cached.get("fetched_at", ""),
                from_cache=True,
                stale=True,
                warning=f"Red no disponible ({error}); se usó caché local.",
            )
        raise ArcGISError(f"No fue posible consultar {url}: {error}")

    # --------------------------------------------------------------- metadata
    def metadata(self, layer_id: int | str | None = None, *, force: bool = False) -> dict[str, Any]:
        path = "" if layer_id is None else str(layer_id)
        return self.get_json(path, {"f": "json"}, force=force).payload

    def flatten_layers(self, metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Devuelve capas y tablas sin depender de IDs fijos."""
        root = metadata or self.metadata()
        out: list[dict[str, Any]] = []
        for layer in root.get("layers", []) or []:
            out.append(dict(layer))
        for table in root.get("tables", []) or []:
            item = dict(table)
            item.setdefault("type", "Table")
            out.append(item)
        return out

    def feature_layers(self, metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return [
            layer
            for layer in self.flatten_layers(metadata)
            if layer.get("type") == "Feature Layer" and layer.get("id") is not None
        ]

    def discover(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Resumen reproducible de capas, IDs, nombres y geometrías vigentes."""
        root = metadata or self.metadata()
        layers = self.flatten_layers(root)
        return {
            "service": self.base_url,
            "service_version": root.get("serviceVersion") or root.get("cimVersion"),
            "description": root.get("description"),
            "max_record_count": root.get("maxRecordCount"),
            "spatial_reference": root.get("spatialReference"),
            "full_extent": root.get("fullExtent"),
            "layers": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "geometry_type": item.get("geometryType"),
                    "parent_layer_id": item.get("parentLayerId"),
                }
                for item in layers
            ],
            "feature_layers": [
                {"id": item.get("id"), "name": item.get("name"), "geometry_type": item.get("geometryType")}
                for item in self.feature_layers(root)
            ],
            "tables": [
                {"id": item.get("id"), "name": item.get("name")}
                for item in root.get("tables", []) or []
            ],
        }

    def layer_fields(self, layer_id: int | str, *, force: bool = False) -> list[dict[str, Any]]:
        return list(self.metadata(layer_id, force=force).get("fields", []) or [])

    # ------------------------------------------------------------------ query
    def count(self, layer_id: int | str, where: str = "1=1", *, force: bool = False) -> int:
        response = self.get_json(
            f"{layer_id}/query",
            {"f": "json", "where": where, "returnCountOnly": "true"},
            force=force,
        )
        payload = response.payload
        if "count" not in payload:
            raise ArcGISError(f"La capa {layer_id} no devolvió count: {payload}")
        return int(payload["count"])

    def query_layer(
        self,
        layer_id: int | str,
        *,
        where: str = "1=1",
        out_fields: str = "*",
        bbox: Iterable[float] | None = None,
        page_size: int | None = None,
        max_features: int | None = None,
        out_sr: int = 4326,
        force: bool = False,
        use_geojson: bool = True,
    ) -> LayerDownload:
        """Descarga paginada. Prefiere GeoJSON y cae a Esri JSON con conversión."""
        layer_meta = self.metadata(layer_id, force=force)
        oid_field = layer_meta.get("objectIdField") or "OBJECTID"
        max_record = int(layer_meta.get("maxRecordCount") or 1000)
        page = max(1, min(int(page_size or max_record), max_record))
        warnings: list[str] = []
        features: list[dict[str, Any]] = []
        offset = 0
        pages = 0
        seen: set[str] = set()
        fmt = "geojson" if use_geojson else "json"
        fetched_at = utc_now()
        from_cache = True

        count_response = self.get_json(
            f"{layer_id}/query",
            {"f": "json", "where": where, "returnCountOnly": "true"},
            force=force,
        )
        total = int(count_response.payload["count"]) if "count" in count_response.payload else None
        from_cache = from_cache and count_response.from_cache

        while True:
            params: dict[str, Any] = {
                "f": fmt,
                "where": where,
                "outFields": out_fields,
                "returnGeometry": "true",
                "outSR": out_sr,
                "resultOffset": offset,
                "resultRecordCount": page,
                "orderByFields": oid_field,
            }
            if bbox is not None:
                xmin, ymin, xmax, ymax = [float(v) for v in bbox]
                params.update(
                    geometry=_stable_json(
                        {
                            "xmin": xmin,
                            "ymin": ymin,
                            "xmax": xmax,
                            "ymax": ymax,
                            "spatialReference": {"wkid": out_sr},
                        }
                    ),
                    geometryType="esriGeometryEnvelope",
                    inSR=out_sr,
                    spatialRel="esriSpatialRelIntersects",
                )
            response = self.get_json(f"{layer_id}/query", params, force=force)
            from_cache = from_cache and response.from_cache
            fetched_at = response.fetched_at or fetched_at
            if response.warning:
                warnings.append(response.warning)
            payload = response.payload
            if "features" not in payload:
                raise ArcGISError(f"Capa {layer_id}: respuesta sin features ({str(payload)[:200]})")
            if payload.get("error"):
                raise ArcGISError(str(payload["error"]))

            batch = payload.get("features", []) or []
            converted: list[dict[str, Any]] = []
            for feature in batch:
                item = self._feature_to_geojson(feature, layer_id, layer_meta)
                fid = str(item.get("id"))
                if fid in seen:
                    continue
                seen.add(fid)
                converted.append(item)
            features.extend(converted)
            pages += 1

            if max_features is not None and len(features) >= max_features:
                features = features[:max_features]
                warnings.append(f"Descarga truncada a {max_features} elementos por configuración.")
                break
            if total is not None and len(features) >= total:
                break
            if not batch:
                break
            if len(batch) < page and not payload.get("exceededTransferLimit"):
                break
            if not converted:
                warnings.append("La paginación no devolvió elementos nuevos; se detuvo para evitar un bucle.")
                break
            # Si el servidor ignora resultOffset, el conjunto de IDs no crece.
            offset += len(batch)

        geometry_type = layer_meta.get("geometryType")
        if total is not None and len(features) != total and not warnings:
            warnings.append(f"Se esperaban {total} registros y se obtuvieron {len(features)}.")
        return LayerDownload(
            layer_id=int(layer_id),
            name=str(layer_meta.get("name", "")),
            geometry_type=geometry_type,
            features=features,
            metadata=layer_meta,
            pages=pages,
            count=total,
            fetched_at=fetched_at,
            from_cache=from_cache,
            warnings=warnings,
        )

    # ------------------------------------------------------------ conversion
    def _feature_to_geojson(
        self, feature: dict[str, Any], layer_id: int | str, layer_meta: dict[str, Any]
    ) -> dict[str, Any]:
        if feature.get("type") == "Feature" and "geometry" in feature:
            # GeoJSON ya convertido por el servidor.
            geom = feature.get("geometry")
            if geom is not None and not self.validate_geojson_geometry(geom):
                geom = None
            item = {
                "type": "Feature",
                "id": feature.get("id", (feature.get("properties") or {}).get("OBJECTID")),
                "geometry": geom,
                "properties": dict(feature.get("properties") or {}),
            }
            return item

        attributes = dict(feature.get("attributes") or {})
        geometry = feature.get("geometry")
        oid = attributes.get(layer_meta.get("objectIdField") or "OBJECTID")
        return {
            "type": "Feature",
            "id": oid,
            "geometry": self.esri_to_geojson_geometry(geometry),
            "properties": attributes,
        }

    @staticmethod
    def esri_to_geojson_geometry(geometry: dict[str, Any] | None) -> dict[str, Any] | None:
        """Convierte point/polyline/polygon Esri JSON (sin curvas) a GeoJSON."""
        if not geometry:
            return None
        if "x" in geometry and "y" in geometry:
            return {"type": "Point", "coordinates": [float(geometry["x"]), float(geometry["y"])]}
        if "paths" in geometry:
            paths = [[[float(x), float(y)] for x, y in path] for path in geometry["paths"]]
            if len(paths) == 1:
                return {"type": "LineString", "coordinates": paths[0]}
            return {"type": "MultiLineString", "coordinates": paths}
        if "rings" in geometry:
            rings = [[[float(x), float(y)] for x, y in ring] for ring in geometry["rings"]]
            return {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}
        if geometry.get("type") in {"Point", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}:
            return geometry
        raise ArcGISError(f"Geometría Esri no soportada: {list(geometry)[:8]}")

    @staticmethod
    def validate_geojson_geometry(geometry: dict[str, Any]) -> bool:
        try:
            kind = geometry["type"]
            coords = geometry["coordinates"]
            if kind == "Point":
                return len(coords) >= 2 and all(isinstance(v, (int, float)) for v in coords[:2])
            if kind in {"LineString", "MultiLineString", "Polygon", "MultiPolygon"}:
                return bool(coords)
        except (KeyError, TypeError, IndexError):
            return False
        return False


def write_json_atomic(path: str | Path, payload: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return path
