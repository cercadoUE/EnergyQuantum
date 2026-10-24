"""Fuentes externas con procedencia explícita.

- OSINERGMIN: infraestructura oficial del SEIN (ArcGIS REST).
- COES: sonda documental; no validación topológica automática.
- OpenStreetMap: complemento opcional, nunca fusionado silenciosamente.
"""

from .arcgis import ArcGISClient, ArcGISError, LayerDownload
from .osinergmin import SERVICE_URL, download_sein, load_snapshot

__all__ = [
    "ArcGISClient",
    "ArcGISError",
    "LayerDownload",
    "SERVICE_URL",
    "download_sein",
    "load_snapshot",
]
