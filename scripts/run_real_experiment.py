"""Ejecuta un experimento reproducible sobre una subred real del SEIN.

Uso:
    python -m scripts.run_real_experiment
    python -m scripts.run_real_experiment --nodes 4 --p 1 --maxiter 10
    python -m scripts.run_real_experiment --skip-qaoa
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.algorithms.classical import brute_force, kernighan_lin, local_search
from src.algorithms.qaoa_solver import solve
from src.models.graph_model import ROOT
from src.models.objective import Objective
from src.models.optimization_instance import build_instance
from src.network.graph_builder import load_network_snapshot
from src.network.subnet_selector import select_subnet
from src.simulation.real_network_failures import compare_metrics, fail_edges, subnet_metrics
from src.utils.export import real_experiment_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", type=int, default=6, help="Nodos de la subred (2..12).")
    parser.add_argument("--component", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--p", type=int, default=1, help="Capas QAOA (1..4).")
    parser.add_argument("--maxiter", type=int, default=60)
    parser.add_argument("--shots", type=int, default=2048)
    parser.add_argument("--time-limit", type=float, default=90.0)
    parser.add_argument("--max-evaluations", type=int, default=400)
    parser.add_argument("--weight-mode", default="length")
    parser.add_argument("--skip-qaoa", action="store_true")
    parser.add_argument(
        "--out", default=str(ROOT / "results" / "real_subnet_experiment.json")
    )
    args = parser.parse_args(argv)

    network = load_network_snapshot()
    subnet = select_subnet(
        network, component_index=args.component, max_nodes=args.nodes
    )
    payload = subnet.to_dict()
    instance = build_instance(payload, weight_mode=args.weight_mode, seed=args.seed)
    data = instance.to_solver_data()
    objective = Objective()
    runs = {
        "Exacto": brute_force(data, objective),
        "Búsqueda local": local_search(data, objective, seed=args.seed),
        "Kernighan–Lin": kernighan_lin(data, objective, seed=args.seed),
    }
    if not args.skip_qaoa:
        runs["QAOA"] = solve(
            data,
            objective,
            p=args.p,
            maxiter=args.maxiter,
            shots=args.shots,
            seed=args.seed,
            optimizer="COBYLA",
            time_limit=args.time_limit,
            max_evaluations=args.max_evaluations,
        )

    before = subnet_metrics(payload, include_failed=False)
    failure_test = None
    if subnet.stats["bridges"]:
        # Orden explícito para que el artefacto sea reproducible entre procesos.
        a, b = sorted(subnet.stats["bridges"], key=lambda pair: tuple(sorted(pair)))[0]
        bridge_id = next(
            edge["id"]
            for edge in payload["edges"]
            if {edge["source"], edge["target"]} == {a, b}
        )
        failed = fail_edges(payload, [bridge_id])
        after = subnet_metrics(failed, include_failed=False)
        failure_test = {
            "failed_edge_id": bridge_id,
            "failed_edge": next(edge for edge in payload["edges"] if edge["id"] == bridge_id),
            "before": before,
            "after": after,
            "comparison": compare_metrics(before, after),
        }

    bundle = json.loads(
        real_experiment_bundle(
            network=network,
            subnet=payload,
            instance=instance,
            runs=runs,
            extra={
                "experiment": (
                    f"subred real de {len(payload['nodes'])} nodos, "
                    f"pesos {args.weight_mode}"
                ),
                "failure_test": failure_test,
                "command": (
                    "python -m scripts.run_real_experiment "
                    f"--nodes {args.nodes} --seed {args.seed} --p {args.p} "
                    f"--maxiter {args.maxiter} --shots {args.shots}"
                ),
            },
        )
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Guardado: {out}")
    for name, run in runs.items():
        print(
            f"{name:<18} H={run.get('objective')} corte={run.get('cut')} "
            f"s={run.get('seconds'):.4f} estado={run.get('status')}"
        )
    if failure_test:
        print(
            f"Falla {failure_test['failed_edge_id']}: "
            f"{failure_test['comparison']['delta']}"
        )
    print(
        f"Subred: {subnet.stats['nodes']} nodos · {subnet.stats['edges']} conexiones · "
        f"{subnet.stats['total_length_km']:.3f} km"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
