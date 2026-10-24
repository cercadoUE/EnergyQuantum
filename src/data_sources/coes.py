"""COES: sonda de disponibilidad, no fuente topológica automática.

El portal público de COES expone el diagrama unifilar y las características del
SEIN como páginas HTML. No se identificó un servicio máquina-máquina estable
con extremos de línea. Por eso este módulo registra evidencia de acceso y
declara explícitamente que no valida conexiones automáticamente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import requests

from ..models.graph_model import ROOT

RAW_DIR = ROOT / "data" / "raw" / "coes"
URLS = {
    "diagrama_unifilar": "https://www.coes.org.pe/Portal/Operacion/CaractSEIN/DiagramaUnifilar",
    "base_datos": "https://www.coes.org.pe/Portal/Operacion/CaractSEIN/BaseDatos",
}
USER_AGENT = "EnergyQuantumPeru/2.0 (research; COES availability probe)"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probe(timeout: float = 30.0, session: requests.Session | None = None) -> dict[str, Any]:
    """Comprueba acceso y busca enlaces documentales; no interpreta topología."""
    session = session or requests.Session()
    session.headers.setdefault("User-Agent", USER_AGENT)
    results: dict[str, Any] = {}
    for key, url in URLS.items():
        try:
            response = session.get(url, timeout=timeout)
            text = response.content.decode("utf-8", errors="replace")
            title = re.search(r"<title>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
            documents = sorted(
                {
                    match
                    for match in re.findall(
                        r'(?:href|src|data)="([^"]+)"', text, flags=re.IGNORECASE
                    )
                    if re.search(r"\.(pdf|xlsx?|csv|zip)(?:$|\?)", match, flags=re.IGNORECASE)
                }
            )
            results[key] = {
                "url": url,
                "accessible": response.status_code == 200,
                "http_status": response.status_code,
                "content_type": response.headers.get("Content-Type"),
                "bytes": len(response.content),
                "title": (title.group(1).strip() if title else None),
                "sha256": sha256(response.content).hexdigest(),
                "document_links": documents[:50],
                "machine_readable_topology": False,
                "note": (
                    "Página HTML. No se identificó un endpoint estable de nodos/aristas; "
                    "no se usa para afirmar conectividad verificada."
                ),
            }
        except requests.RequestException as exc:
            results[key] = {
                "url": url,
                "accessible": False,
                "http_status": None,
                "error": str(exc),
                "machine_readable_topology": False,
                "note": "Sin acceso en esta ejecución; no se infiere nada.",
            }
    return {
        "institution": "COES",
        "probed_at_utc": utc_now(),
        "urls": results,
        "validation_status": "NO_AUTOMATIZADA",
        "limitations": [
            "El diagrama unifilar es un documento gráfico, no una tabla de aristas.",
            "No se declara ninguna conexión como validada por COES.",
            "La contrastación documental manual queda fuera de esta versión.",
        ],
    }


def save_probe(raw_dir: str | Path = RAW_DIR, **kwargs: Any) -> dict[str, Any]:
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = probe(**kwargs)
    path = raw_dir / "probe.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def validated_connections(*_: Any, **__: Any) -> list[dict[str, Any]]:
    """Contrato explícito: esta versión no dispone de validación COES automática."""
    return []
