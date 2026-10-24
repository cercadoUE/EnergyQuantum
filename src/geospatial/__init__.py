"""Procesamiento geoespacial sin dependencias nativas obligatorias."""

from .geometry import (
    geometry_length_km,
    haversine_km,
    name_variants,
    normalize_text,
    simplify_geometry,
    validate_geometry,
)
from .processing import load_processed, process_snapshot, save_processed

__all__ = [
    "geometry_length_km",
    "haversine_km",
    "name_variants",
    "normalize_text",
    "simplify_geometry",
    "validate_geometry",
    "load_processed",
    "process_snapshot",
    "save_processed",
]
