"""Descarga el Mapa del SEIN de OSINERGMIN a data/raw/osinergmin.

Uso:
    python -m scripts.download_sein
    python -m scripts.download_sein --force
    python -m scripts.download_sein --probe-coes
"""
from __future__ import annotations

import argparse
import json
import sys

from src.data_sources.arcgis import ArcGISClient
from src.data_sources.coes import save_probe
from src.data_sources.osinergmin import RAW_DIR, SERVICE_URL, download_sein
from src.geospatial.processing import PROCESSED_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Ignora la caché HTTP y vuelve a descargar.")
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-features", type=int, default=None)
    parser.add_argument(
        "--types",
        default="substation,line,generation",
        help="Roles separados por coma: substation,line,generation.",
    )
    parser.add_argument("--probe-coes", action="store_true", help="Registra evidencia de acceso a COES.")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)

    client = ArcGISClient(SERVICE_URL, timeout=args.timeout)
    types = [item.strip() for item in args.types.split(",") if item.strip()]
    try:
        manifest = download_sein(
            client=client,
            raw_dir=args.raw_dir,
            force=args.force,
            page_size=args.page_size,
            max_features=args.max_features,
            types=types,
        )
    except Exception as exc:  # noqa: BLE001 - mensaje operativo
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.probe_coes:
        probe = save_probe()
        print(f"COES: {probe['validation_status']} ({', '.join(str(v.get('http_status')) for v in probe['urls'].values())})")

    print(f"Manifiesto: {args.raw_dir}/manifest.json")
    print(f"Capas: {len(manifest['layers'])} · registros: {manifest['record_total']}")
    for layer in manifest["layers"]:
        print(
            f"  {layer['layer_id']:>2} {layer['role']:<11} {layer['records']:>5} "
            f"{layer['layer_name']} [{layer['file']}]"
        )
    if manifest["errors"]:
        print("Advertencias:", file=sys.stderr)
        for error in manifest["errors"]:
            print(f"  capa {error['layer_id']}: {error['error']} (previa={error['kept_previous']})", file=sys.stderr)
        if not manifest["layers"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
