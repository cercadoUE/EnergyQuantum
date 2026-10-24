"""Pantallas de datos reales del SEIN.

Se mantienen separadas de las pantallas sintéticas para no alterar sus
contratos. Ninguna pantalla descarga datos: leen snapshots locales generados
por scripts/download_sein.py y scripts/build_network.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from ..algorithms.classical import brute_force, kernighan_lin, local_search
from ..algorithms.qaoa_solver import solve
from ..data_sources.osinergmin import RAW_DIR
from ..experiments.metrics import gap, optimal_probability
from ..geospatial.processing import PROCESSED_DIR
from ..models.graph_model import ROOT
from ..models.objective import Objective
from ..models.optimization_instance import InstanceError, build_instance
from ..network.graph_builder import NETWORK_DIR, load_network_snapshot
from ..network.subnet_selector import (
    SubnetError,
    availability_by_size,
    component_summaries,
    select_subnet,
)
from ..simulation.real_network_failures import compare_metrics, fail_edges, subnet_metrics
from ..utils.export import (
    config_json,
    edges_csv,
    graphml,
    nodes_csv,
    provenance_json,
    real_experiment_bundle,
    results_csv,
)
from ..visualization.network import network_figure
from ..visualization.peru_map import peru_map, subnet_map

REAL_PAGES = [
    "Mapa eléctrico del Perú",
    "Explorador de subredes",
    "Red real · optimización",
    "Fuentes y metodología",
]

WEIGHT_OPTIONS = {
    "A · Longitud geográfica (km)": "length",
    "B · Costo normalizado por mediana": "normalized",
    "C · Pesos personalizados (JSON)": "custom",
    "D · Escenario sintético (Uniforme 1–10)": "synthetic",
}
DEMAND_OPTIONS = {
    "Uniforme abstracta (1 u.s./nodo)": "uniform",
    "Proxy por capacidad de transformación": "capacity_proxy",
}


def _clear_failure_selection() -> None:
    """Callback: limpia fallas y el estado visual del multiselect antes del rerun."""
    st.session_state["real_failed_edges"] = []
    st.session_state["real-failure-select"] = []


def _stamp(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return 0, 0


@st.cache_data(show_spinner=False)
def _read_json(path: str, stamp: tuple[int, int]) -> dict[str, Any]:
    del stamp
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _network_path() -> Path:
    return NETWORK_DIR / "sein_network.json"


def load_network_safe() -> dict[str, Any] | None:
    path = _network_path()
    if not path.exists():
        st.warning(
            "No hay una red procesada. Ejecute `python -m scripts.download_sein` y "
            "`python -m scripts.build_network` para crear el snapshot local."
        )
        st.code(
            "python -m scripts.download_sein\npython -m scripts.build_network\n"
            "python -m scripts.validate_network",
            language="powershell",
        )
        return None
    try:
        return _read_json(str(path), _stamp(path))
    except (OSError, ValueError) as exc:
        st.error(f"No se pudo leer la red procesada: {exc}")
        return None


def _voltage_label(value: float) -> str:
    return f"{value:g} kV"


def _voltage_values(labels: list[str]) -> list[float]:
    return [float(label.replace(" kV", "")) for label in labels]


def _filtered_tables(
    network: dict[str, Any],
    departments: list[str],
    voltages: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    deps = {item.upper() for item in departments}
    volts = set(_voltage_values(voltages))
    nodes = [
        node
        for node in network.get("nodes", [])
        if (not deps or str(node.get("department") or "").upper() in deps)
        and (
            not volts
            or any(
                abs(float(v) - value) <= 0.6
                for v in (node.get("voltages_kv") or [node.get("voltage_kv")])
                if v is not None
                for value in volts
            )
        )
    ]
    node_ids = {node["id"] for node in nodes}
    edges = [
        edge
        for edge in network.get("edges", [])
        if edge.get("source") in node_ids
        and edge.get("target") in node_ids
        and (not volts or any(abs(float(edge.get("voltage_kv") or -1) - value) <= 0.6 for value in volts))
    ]
    node_frame = pd.DataFrame(
        [
            {
                "Nombre": node.get("name"),
                "Departamento": node.get("department"),
                "Tensión (kV)": node.get("voltage_kv"),
                "Capacidad (MVA)": node.get("capacity_mva"),
                "Estado": node.get("state"),
                "Componente": node.get("component"),
                "Conectada": node.get("in_verified_graph"),
                "ID": node.get("id"),
                "Origen": ", ".join(str(item) for item in node.get("source_ids", [])),
            }
            for node in nodes
        ]
    )
    edge_frame = pd.DataFrame(
        [
            {
                "Origen": edge.get("source_name"),
                "Destino": edge.get("target_name"),
                "Tensión (kV)": edge.get("voltage_kv"),
                "Longitud (km)": edge.get("length_km"),
                "Líneas": edge.get("line_count"),
                "Validación": edge.get("validation"),
                "COES": "No validado",
                "ID": edge.get("id"),
            }
            for edge in edges
        ]
    )
    return node_frame, edge_frame


# ------------------------------------------------------------------- map page
def render_map_page() -> None:
    network = load_network_safe()
    if network is None:
        return
    nodes = network.get("nodes", [])
    edges = network.get("edges", [])
    quality = network.get("quality", {})
    st.markdown("### Infraestructura del SEIN sobre el mapa del Perú")
    st.caption(
        "Geometrías y atributos descargados de OSINERGMIN. Las conexiones del mapa son "
        "solo líneas con extremos explícitos resueltos; las no verificadas no se dibujan como aristas del grafo."
    )
    cols = st.columns(4)
    cols[0].metric("Subestaciones", len(nodes))
    cols[1].metric("Líneas verificadas", quality.get("lines_verified", 0))
    cols[2].metric("Conexiones agregadas", len(edges))
    cols[3].metric("Componentes con aristas", quality.get("components_with_edges", 0))

    departments = sorted({node.get("department") for node in nodes if node.get("department")})
    voltage_options = sorted(
        {
            float(v)
            for node in nodes
            for v in (node.get("voltages_kv") or [node.get("voltage_kv")])
            if v is not None
        }
    )
    with st.expander("Filtros del mapa", expanded=True):
        left, middle, right = st.columns([2, 2, 1])
        selected_departments = left.multiselect("Departamentos", departments, key="map-departments")
        selected_voltages = middle.multiselect(
            "Niveles de tensión", [_voltage_label(v) for v in voltage_options], key="map-voltages"
        )
        max_lines = right.slider("Máximo de líneas", 100, 2500, 1000, 100, key="map-max-lines")
        toggles = st.columns(3)
        show_lines = toggles[0].checkbox("Mostrar líneas", True, key="map-show-lines")
        show_stations = toggles[1].checkbox("Mostrar subestaciones", True, key="map-show-stations")
        show_generation = toggles[2].checkbox("Mostrar centrales", False, key="map-show-generation")

    figure = peru_map(
        network,
        departments=selected_departments,
        voltages=_voltage_values(selected_voltages),
        show_lines=show_lines,
        show_stations=show_stations,
        show_generation=show_generation,
        max_lines=max_lines,
    )
    st.plotly_chart(figure, width="stretch", config={"scrollZoom": True, "displaylogo": False})
    meta = getattr(figure.layout, "meta", None)
    if isinstance(meta, dict):
        st.caption(
            f"Se dibujan {meta.get('shown_lines', 0)} líneas y "
            f"{meta.get('selected_stations', 0)} subestaciones tras los filtros. "
            "Use los controles del mapa para acercar y consultar atributos."
        )

    node_frame, edge_frame = _filtered_tables(network, selected_departments, selected_voltages)
    tabs = st.tabs(["Subestaciones", "Conexiones", "Leyenda y fuente"])
    with tabs[0]:
        st.dataframe(node_frame, hide_index=True, width="stretch", height=280)
    with tabs[1]:
        st.dataframe(edge_frame, hide_index=True, width="stretch", height=280)
        st.caption("Cada conexión agregada conserva los IDs de sus líneas y su estado de validación.")
    with tabs[2]:
        st.markdown(
            "- **500 kV**: violeta · **220 kV**: rojo · **138 kV**: naranja · **60 kV**: azul · otros: gris.\n"
            "- **Fuente**: OSINERGMIN, Mapa del SEIN (ArcGIS REST).\n"
            "- **Conexión verificada**: `NODO_SALIDA` y `NODO_LLEGADA` coinciden con estaciones de la fuente.\n"
            "- **No verificado por COES**: no se declara validación COES en esta versión.\n"
            "- Los cruces geográficos y las cercanías no crean conexiones."
        )
        st.download_button(
            "Descargar resumen de calidad (JSON)",
            json.dumps(quality, ensure_ascii=False, indent=2),
            "sein_topology_report.json",
            "application/json",
            key="map-quality-download",
        )


# -------------------------------------------------------------- explorer page
def _component_label(component: dict[str, Any]) -> str:
    deps = ", ".join(component.get("departments", [])[:3]) or "sin departamento"
    return (
        f"Componente {component['index']} · {component['nodes']} nodos · "
        f"{component['edges']} conexiones · {component['total_length_km']:.0f} km · {deps}"
    )


def render_explorer_page() -> None:
    network = load_network_safe()
    if network is None:
        return
    components = component_summaries(network)
    if not components:
        st.error("La red no contiene componentes con conexiones verificadas.")
        return
    st.markdown("### Construir una subred conectada")
    st.caption(
        "La subred se extrae de aristas verificadas. Puede elegir una componente, filtrar por "
        "departamento/tensión o fijar nodos manualmente; si la selección no es conexa, se informa."
    )
    with st.expander("Componentes verificadas", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Componente": item["index"],
                        "Nodos": item["nodes"],
                        "Conexiones": item["edges"],
                        "Longitud (km)": item["total_length_km"],
                        "Departamentos": ", ".join(item["departments"]),
                        "Tensiones (kV)": ", ".join(f"{v:g}" for v in item["voltages_kv"]),
                    }
                    for item in components
                ]
            ),
            hide_index=True,
            width="stretch",
        )

    component_choice = st.selectbox(
        "Componente",
        options=list(range(len(components))),
        format_func=lambda index: _component_label(components[index]),
        key="subnet-component",
    )
    component = components[component_choice]
    node_by_id = {node["id"]: node for node in network.get("nodes", [])}
    component_nodes = [node_by_id[node_id] for node_id in component["node_ids"]]
    component_departments = sorted({node.get("department") for node in component_nodes if node.get("department")})
    component_voltages = sorted(
        {
            float(v)
            for node in component_nodes
            for v in (node.get("voltages_kv") or [node.get("voltage_kv")])
            if v is not None
        }
    )
    filters = st.columns(3)
    selected_departments = filters[0].multiselect(
        "Filtrar departamentos", component_departments, key="subnet-departments"
    )
    selected_voltages = filters[1].multiselect(
        "Filtrar tensiones", [_voltage_label(v) for v in component_voltages], key="subnet-voltages"
    )
    max_nodes = filters[2].select_slider(
        "Máximo de nodos", options=[4, 6, 8, 10, 12], value=6, key="subnet-max-nodes"
    )
    seed_options = [node["id"] for node in component_nodes]
    seed_id = st.selectbox(
        "Semilla (opcional)",
        options=[None] + seed_options,
        format_func=lambda value: "Automática (mayor grado)" if value is None else node_by_id[value]["name"],
        key="subnet-seed",
    )
    availability = availability_by_size(
        network,
        [4, 6, 8, 10, 12],
        departments=selected_departments,
        voltages=_voltage_values(selected_voltages),
    )
    st.caption(" · ".join(item["message"] for item in availability.values()))

    manual = st.multiselect(
        "Nodos manuales (opcional; reemplaza la expansión automática)",
        options=seed_options,
        format_func=lambda value: f"{node_by_id[value]['name']} · {node_by_id[value].get('department') or '—'}",
        key="subnet-manual",
    )
    try:
        subnet = select_subnet(
            network,
            departments=selected_departments or None,
            voltages=_voltage_values(selected_voltages) or None,
            component_index=None if (selected_departments or selected_voltages) else component["index"],
            max_nodes=max_nodes,
            seed_node=seed_id,
            node_ids=manual or None,
        )
    except SubnetError as exc:
        st.error(str(exc))
        return

    st.success(subnet.selection["message"])
    stats = st.columns(4)
    stats[0].metric("Nodos", subnet.stats["nodes"])
    stats[1].metric("Conexiones", subnet.stats["edges"])
    stats[2].metric("Longitud (km)", f"{subnet.stats['total_length_km']:.1f}")
    stats[3].metric("Puentes", len(subnet.stats["bridges"]))
    st.plotly_chart(
        subnet_map(network, subnet.to_dict(), show_generation=False),
        width="stretch",
        config={"scrollZoom": True, "displaylogo": False},
    )
    action = st.button("Usar esta subred en optimización", type="primary", key="subnet-use")
    if action:
        st.session_state["real_subnet"] = subnet.to_dict()
        st.session_state["real_failed_edges"] = []
        st.session_state.pop("real-failure-select", None)
        st.success("Subred cargada. Abra «Red real · optimización».")

    node_tab, edge_tab, selection_tab = st.tabs(["Nodos", "Conexiones", "Selección y exportación"])
    with node_tab:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Nombre": node.get("name"),
                        "Departamento": node.get("department"),
                        "Tensión (kV)": node.get("voltage_kv"),
                        "Capacidad (MVA)": node.get("capacity_mva"),
                        "Componente": node.get("component"),
                        "ID": node.get("id"),
                    }
                    for node in subnet.nodes
                ]
            ),
            hide_index=True,
            width="stretch",
            height=260,
        )
        st.caption("Los IDs originales se conservan; los atributos completos están en la exportación JSON.")
    with edge_tab:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Origen": edge.get("source_name"),
                        "Destino": edge.get("target_name"),
                        "Tensión (kV)": edge.get("voltage_kv"),
                        "Longitud (km)": edge.get("length_km"),
                        "Líneas": edge.get("line_count"),
                        "Validación": edge.get("validation"),
                        "ID": edge.get("id"),
                    }
                    for edge in subnet.edges
                ]
            ),
            hide_index=True,
            width="stretch",
            height=260,
        )
        edge_choice = st.selectbox(
            "Inspeccionar una conexión",
            options=[edge["id"] for edge in subnet.edges],
            format_func=lambda value: next(
                f"{edge['source_name']} ↔ {edge['target_name']} · {edge['length_km']} km"
                for edge in subnet.edges
                if edge["id"] == value
            ),
            key="subnet-edge-inspect",
        )
        edge = next(edge for edge in subnet.edges if edge["id"] == edge_choice)
        st.json(
            {
                "id": edge["id"],
                "extremos": [edge["source"], edge["target"]],
                "nombres": [edge["source_name"], edge["target_name"]],
                "tensiones_kv": edge["voltages_kv"],
                "longitud_km": edge["length_km"],
                "lineas": edge["line_ids"],
                "validacion": edge["validation"],
                "coes_validado": False,
                "procedencia": "DERIVADO de extremos explícitos OSINERGMIN",
            },
            expanded=True,
        )
    with selection_tab:
        st.json(subnet.selection, expanded=True)
        st.download_button(
            "Subred JSON",
            json.dumps(subnet.to_dict(), ensure_ascii=False, indent=2),
            "sein_subnet.json",
            "application/json",
            key="subnet-json",
        )
        st.download_button(
            "Nodos CSV", nodes_csv(subnet.nodes), "sein_subnet_nodes.csv", "text/csv", key="subnet-nodes-csv"
        )
        st.download_button(
            "Conexiones CSV",
            edges_csv(subnet.edges),
            "sein_subnet_edges.csv",
            "text/csv",
            key="subnet-edges-csv",
        )
        st.download_button(
            "Grafo GraphML",
            graphml(subnet.to_dict()),
            "sein_subnet.graphml",
            "application/graphml+xml",
            key="subnet-graphml",
        )


# ----------------------------------------------------------- optimization page
def _auto_subnet(network: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return select_subnet(network, component_index=0, max_nodes=6).to_dict()
    except SubnetError:
        return None


def _run_all(data: dict[str, Any], objective: Objective, seed: int) -> dict[str, Any]:
    runs: dict[str, Any] = {}
    runs["Exacto"] = brute_force(data, objective)
    runs["Búsqueda local"] = local_search(data, objective, seed=seed)
    runs["Kernighan–Lin"] = kernighan_lin(data, objective, seed=seed)
    return runs


def _metrics_row(runs: dict[str, Any], optimum: float | None, qaoa: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    for name, run in runs.items():
        rows.append(
            {
                "Método": name,
                "H": run.get("objective"),
                "Corte (pesos)": run.get("cut"),
                "Factible": (run.get("validation") or {}).get("feasible"),
                "Tiempo (s)": round(float(run.get("seconds") or 0), 4),
                "Brecha vs exacto": gap(run.get("objective"), optimum) if optimum is not None else None,
                "Evaluaciones": run.get("evaluations"),
            }
        )
    return rows


def _current_history() -> dict[str, Any]:
    return st.session_state.setdefault("real_history", {})


def render_optimization_page(alpha: float, beta: float, seed: int) -> None:
    network = load_network_safe()
    if network is None:
        return
    subnet = st.session_state.get("real_subnet")
    if not subnet:
        subnet = _auto_subnet(network)
        if subnet:
            st.session_state["real_subnet"] = subnet
            st.info("Se cargó automáticamente una subred conectada de 6 nodos de la mayor componente.")
        else:
            st.warning("No se pudo seleccionar una subred automáticamente. Use el Explorador de subredes.")
            return

    st.markdown("### Optimización sobre la subred seleccionada")
    st.caption(
        "Los algoritmos existentes reciben una instancia adaptada. La topología es verificada; "
        "demanda, pesos y generación son supuestos explícitos del escenario."
    )
    top = st.columns(4)
    top[0].metric("Nodos", len(subnet.get("nodes", [])))
    top[1].metric("Conexiones", len(subnet.get("edges", [])))
    top[2].metric("Longitud (km)", f"{subnet.get('stats', {}).get('total_length_km', 0):.1f}")
    top[3].metric("Componentes", subnet.get("stats", {}).get("components"))

    config = st.columns(3)
    weight_label = config[0].selectbox("Modo de peso", list(WEIGHT_OPTIONS), key="real-weight-mode")
    demand_label = config[1].selectbox("Demanda de escenario", list(DEMAND_OPTIONS), key="real-demand-mode")
    demand_value = config[2].number_input(
        "Demanda uniforme por nodo", 0.1, 100.0, 1.0, 0.1, key="real-demand-value"
    )
    weight_mode = WEIGHT_OPTIONS[weight_label]
    custom_weights = None
    if weight_mode == "custom":
        default = {edge["id"]: float(edge.get("length_km") or 1.0) for edge in subnet.get("edges", [])}
        raw = st.text_area(
            "Pesos personalizados (JSON id → valor)",
            json.dumps(default, ensure_ascii=False, indent=2),
            height=140,
            key="real-custom-weights",
        )
        try:
            custom_weights = json.loads(raw)
        except ValueError as exc:
            st.error(f"JSON de pesos inválido: {exc}")
            return

    failed_ids = st.session_state.get("real_failed_edges", [])
    known_edge_ids = {edge["id"] for edge in subnet.get("edges", [])}
    failed_ids = [edge_id for edge_id in failed_ids if edge_id in known_edge_ids]
    st.session_state["real_failed_edges"] = failed_ids
    try:
        instance = build_instance(
            subnet,
            weight_mode=weight_mode,
            demand_mode=DEMAND_OPTIONS[demand_label],
            demand_value=demand_value,
            custom_weights=custom_weights,
            seed=int(seed),
            failed_edge_ids=failed_ids,
            source_metadata=(network.get("source") or {}),
        )
        data = instance.to_solver_data()
    except (InstanceError, ValueError) as exc:
        st.error(f"No se pudo construir la instancia: {exc}")
        return
    objective = Objective(alpha, beta)
    fingerprint = instance.fingerprint()
    st.caption(
        f"Huella de instancia: `{fingerprint[:16]}…` · pesos {instance.scenario_metadata['weight']['label']} · "
        f"demanda {instance.scenario_metadata['demand']['label']}."
    )
    if instance.scenario_metadata["weight"]["provenance"] == "SIMULADO" or instance.scenario_metadata["demand"]["provenance"] == "SIMULADO":
        st.warning(
            "Este escenario contiene supuestos simulados. No son costos oficiales ni demanda oficial; "
            "consulte «Fuentes y metodología»."
        )

    with st.expander("Instancia enviada a los solucionadores", expanded=False):
        st.json(
            {
                "nodos": len(instance.nodes),
                "aristas": len(instance.edges),
                "restricciones": instance.constraints,
                "escenario": instance.scenario_metadata,
                "pesos": [
                    {"id": edge.id, "peso": round(edge.weight, 4), "longitud_km": edge.length_km, "fallada": edge.failed}
                    for edge in instance.edges
                ],
            },
            expanded=False,
        )

    # Historial por huella: permite comparar antes/después de una falla.
    history = _current_history()
    current = history.get(fingerprint)
    action_cols = st.columns(2)
    run_classical = action_cols[0].button("Ejecutar métodos clásicos", type="primary", key="real-run-classical")
    qaoa_max_qubits = 10
    run_qaoa = action_cols[1].button(
        f"Ejecutar QAOA ({len(instance.nodes)} qubits)",
        disabled=len(instance.nodes) > qaoa_max_qubits,
        key="real-run-qaoa",
    )
    if len(instance.nodes) > qaoa_max_qubits:
        st.caption(f"QAOA deshabilitado por encima de {qaoa_max_qubits} qubits en esta pantalla.")
    qaoa_config = st.columns(3)
    p_layers = qaoa_config[0].slider("Capas p", 1, 4, 1, key="real-qaoa-p")
    shots = qaoa_config[1].selectbox("Mediciones", [512, 2048, 8192], index=1, key="real-qaoa-shots")
    maxiter = qaoa_config[2].slider("Iteraciones", 10, 150, 60, 10, key="real-qaoa-maxiter")

    if run_classical or run_qaoa:
        runs: dict[str, Any] = dict(current["runs"]) if current else {}
        with st.spinner("Ejecutando sobre la misma instancia…"):
            if run_classical:
                runs.update(_run_all(data, objective, int(seed)))
            if run_qaoa and len(instance.nodes) <= qaoa_max_qubits:
                runs["QAOA"] = solve(
                    data,
                    objective,
                    p=p_layers,
                    maxiter=maxiter,
                    shots=shots,
                    seed=int(seed),
                    optimizer="COBYLA",
                    time_limit=90,
                    max_evaluations=400,
                )
        history[fingerprint] = {
            "fingerprint": fingerprint,
            "runs": runs,
            "failed_edge_ids": list(failed_ids),
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "weight": instance.scenario_metadata["weight"],
            "demand": instance.scenario_metadata["demand"],
        }
        current = history[fingerprint]
        # Mantiene un historial acotado en memoria de sesión.
        if len(history) > 8:
            for key in sorted(history, key=lambda item: history[item]["created_at_utc"])[:-8]:
                history.pop(key, None)
        st.session_state["real_history"] = history

    if current:
        runs = current["runs"]
        optimum = runs.get("Exacto", {}).get("objective")
        qaoa = runs.get("QAOA")
        rows = _metrics_row(runs, optimum, qaoa)
        st.markdown("#### Comparación de solucionadores")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if qaoa and qaoa.get("objective") is not None:
            st.metric(
                "Frecuencia de medir un óptimo factible (QAOA)",
                f"{optimal_probability(qaoa, data, objective, optimum):.2%}" if optimum is not None else "—",
            )
        chart_cols = st.columns(2)
        frame = pd.DataFrame(rows)
        chart_cols[0].plotly_chart(
            px.bar(frame, x="Método", y="H", color="Método", title="Costo objetivo"),
            width="stretch",
            key="real-cost-chart",
        )
        chart_cols[1].plotly_chart(
            px.bar(frame, x="Método", y="Tiempo (s)", color="Método", title="Tiempo medido"),
            width="stretch",
            key="real-time-chart",
        )
        if qaoa and "counts" in qaoa:
            top_counts = sorted(qaoa["counts"].items(), key=lambda item: item[1], reverse=True)[:20]
            st.plotly_chart(
                px.bar(
                    x=[item[0] for item in top_counts],
                    y=[item[1] for item in top_counts],
                    labels={"x": "Bitstring (qubit 0 a la derecha)", "y": "Conteos"},
                    title="20 mediciones más frecuentes",
                ),
                width="stretch",
                key="real-qaoa-hist",
            )
        if qaoa and qaoa.get("trace"):
            st.plotly_chart(
                px.line(y=qaoa["trace"], labels={"index": "Evaluación", "y": "H esperado"}, title="Convergencia QAOA"),
                width="stretch",
                key="real-qaoa-trace",
            )
        if runs.get("Exacto", {}).get("bits") is not None:
            st.markdown("#### Partición del mejor resultado exacto")
            st.plotly_chart(
                network_figure(data, runs["Exacto"]["bits"]),
                width="stretch",
                key="real-partition-figure",
            )
            st.caption(
                "Colores = etiquetas binarias sobre posiciones normalizadas; no son coordenadas del mapa. "
                "Una etiqueta puede contener varias componentes."
            )

        # Comparación con otra ejecución del historial.
        alternatives = [key for key in history if key != fingerprint]
        if alternatives:
            baseline = st.selectbox(
                "Comparar con una ejecución anterior",
                options=["—"] + alternatives,
                format_func=lambda value: (
                    "—"
                    if value == "—"
                    else f"{value[:12]} · fallas {len(history[value]['failed_edge_ids'])} · {history[value]['created_at_utc']}"
                ),
                key="real-compare-baseline",
            )
            if baseline != "—" and history[baseline]["runs"].get("Exacto"):
                before = history[baseline]["runs"]["Exacto"]
                after = runs.get("Exacto")
                if after:
                    delta = st.columns(2)
                    delta[0].metric("H exacto anterior", f"{before.get('objective'):.6f}")
                    delta[1].metric("H exacto actual", f"{after.get('objective'):.6f}", delta=f"{after.get('objective') - before.get('objective'):+.6f}")

    # ------------------------------------------------------------ fallas
    st.divider()
    st.markdown("#### Simulador de fallas de conexión")
    st.caption(
        "Marcar una conexión fuera de servicio cambia la topología. No se estima energía no "
        "suministrada: no hay demanda, generación ni flujo modelados."
    )
    edge_labels = {
        f"{edge['id']} · {edge['source_name']} ↔ {edge['target_name']}": edge["id"]
        for edge in subnet.get("edges", [])
    }
    selected_failures = st.multiselect(
        "Conexiones fuera de servicio",
        options=list(edge_labels),
        default=[label for label, value in edge_labels.items() if value in failed_ids],
        key="real-failure-select",
    )
    fail_cols = st.columns(3)
    apply_failure = fail_cols[0].button("Aplicar fallas", key="real-apply-failures")
    fail_cols[1].button(
        "Quitar fallas",
        key="real-clear-failures",
        on_click=_clear_failure_selection,
    )
    if apply_failure:
        st.session_state["real_failed_edges"] = [edge_labels[label] for label in selected_failures]
        st.rerun()

    before_metrics = subnet_metrics(subnet, include_failed=False)
    failed_subnet = fail_edges(subnet, failed_ids)
    after_metrics = subnet_metrics(failed_subnet, include_failed=False)
    st.dataframe(
        pd.DataFrame(
            [
                {"Indicador": key, "Antes": before_metrics.get(key), "Después": after_metrics.get(key)}
                for key in (
                    "edges_active",
                    "edges_failed",
                    "components",
                    "largest_component",
                    "isolated_nodes",
                    "total_length_km_active",
                )
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(after_metrics["note"])

    # ---------------------------------------------------------- exportación
    with st.expander("Exportar experimento", expanded=False):
        extra = {
            "instance_fingerprint": fingerprint,
            "failed_edge_ids": list(failed_ids),
            "history": {
                key: {
                    "failed_edge_ids": value["failed_edge_ids"],
                    "created_at_utc": value["created_at_utc"],
                    "methods": list(value["runs"]),
                }
                for key, value in history.items()
            },
        }
        st.download_button(
            "Experimento completo JSON",
            real_experiment_bundle(
                network=network,
                subnet=subnet,
                instance=instance,
                runs=current["runs"] if current else {},
                extra=extra,
            ),
            "sein_experiment.json",
            "application/json",
            key="real-exp-json",
        )
        st.download_button(
            "Resultados CSV",
            results_csv(current["runs"] if current else {}),
            "sein_results.csv",
            "text/csv",
            key="real-exp-csv",
        )
        st.download_button(
            "Configuración experimental JSON",
            config_json(instance, extra=extra),
            "sein_experiment_config.json",
            "application/json",
            key="real-exp-config",
        )
        st.download_button(
            "Metadatos de procedencia JSON",
            provenance_json(network=network, subnet=subnet, extra=extra),
            "sein_provenance.json",
            "application/json",
            key="real-exp-provenance",
        )
        st.download_button(
            "Nodos CSV", nodes_csv(subnet.get("nodes", [])), "sein_nodes.csv", "text/csv", key="real-exp-nodes"
        )
        st.download_button(
            "Conexiones CSV",
            edges_csv(subnet.get("edges", [])),
            "sein_edges.csv",
            "text/csv",
            key="real-exp-edges",
        )
        st.download_button(
            "Grafo GraphML",
            graphml(subnet),
            "sein_subnet.graphml",
            "application/graphml+xml",
            key="real-exp-graphml",
        )


# --------------------------------------------------------------- sources page
def _read_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return _read_json(str(path), _stamp(path))
    except (OSError, ValueError):
        return None


def render_sources_page() -> None:
    st.markdown("### Fuentes, procedencia y metodología")
    st.caption(
        "Esta sección distingue datos oficiales descargados, transformaciones derivadas y "
        "supuestos simulados. Un resultado calculado por EnergyQuantum no es un dato oficial."
    )
    manifest = _read_optional(RAW_DIR / "manifest.json")
    network = load_network_safe()
    processing = _read_optional(PROCESSED_DIR / "sein_processing_report.json")
    coes = _read_optional(ROOT / "data" / "raw" / "coes" / "probe.json")

    tags = st.columns(4)
    tags[0].markdown("**OFICIAL**\n\nGeometrías y atributos OSINERGMIN descargados.")
    tags[1].markdown("**DERIVADO**\n\nIdentidad de nodos, extremos resueltos, aristas y pesos.")
    tags[2].markdown("**VALIDADO**\n\nSolo si se documenta evidencia explícita. COES: no automatizado.")
    tags[3].markdown("**SIMULADO**\n\nDemanda, generación, fallas y pesos sintéticos de escenario.")

    if manifest:
        st.markdown("#### Descarga OSINERGMIN")
        cols = st.columns(4)
        cols[0].metric("Institución", manifest.get("institution", "OSINERGMIN"))
        cols[1].metric("Capas", len(manifest.get("layers", [])))
        cols[2].metric("Registros", manifest.get("record_total", 0))
        cols[3].metric("Errores", len(manifest.get("errors", [])))
        st.code(manifest.get("service", ""), language="text")
        st.caption(f"Fecha de manifiesto: {manifest.get('downloaded_at_utc')} · etiqueta: {manifest.get('provenance')}")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID": layer["layer_id"],
                        "Capa": layer["layer_name"],
                        "Rol": layer["role"],
                        "Registros": layer["records"],
                        "Tensión (nombre)": layer.get("voltage_kv_from_name"),
                        "Geometría": layer.get("geometry_type"),
                        "Archivo": layer.get("file"),
                        "Fecha": layer.get("downloaded_at_utc"),
                        "Caché": layer.get("from_cache"),
                        "Advertencias": "; ".join(layer.get("warnings", [])),
                    }
                    for layer in manifest.get("layers", [])
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        with st.expander("Campos utilizados y transformaciones"):
            st.json(
                {
                    "campos_estaciones": [
                        "OBJECTID",
                        "NOMBRE",
                        "COD_SE",
                        "TENSION_NOM",
                        "EMPRESA",
                        "DEPARTAMENTO",
                        "CAPACIDAD",
                        "ESTADO",
                    ],
                    "campos_lineas": [
                        "OBJECTID",
                        "COD_LINEA",
                        "NOMBRE",
                        "TENSION_NOM",
                        "LONGITUD",
                        "NODO_SALIDA",
                        "NODO_LLEGADA",
                        "ESTADO",
                    ],
                    "transformaciones": (processing or {}).get("transformations", []),
                    "limitaciones_procesamiento": (processing or {}).get("limitations", []),
                },
                expanded=False,
            )
    else:
        st.info("No hay manifiesto de descarga. Ejecute `python -m scripts.download_sein`.")

    if network:
        quality = network.get("quality", {})
        st.markdown("#### Topología derivada y validación")
        cols = st.columns(4)
        cols[0].metric("Estaciones", quality.get("nodes_total", 0))
        cols[1].metric("Líneas verificadas", quality.get("lines_verified", 0))
        cols[2].metric("Líneas no verificadas", quality.get("lines_unverified", 0))
        cols[3].metric("Conexiones agregadas", quality.get("edges_verified", 0))
        st.markdown(
            f"- **Criterio:** {network.get('metadata', {}).get('rule')}\n"
            f"- **Significado:** {network.get('metadata', {}).get('verified_means')}\n"
            f"- **COES:** {network.get('metadata', {}).get('coes')}\n"
            f"- **Generación:** {network.get('metadata', {}).get('generation')}\n"
            f"- **Demanda:** {network.get('metadata', {}).get('demand')}"
        )
        st.json(
            {
                "checks": quality.get("checks"),
                "componentes": quality.get("components_verified"),
                "mayor_componente": quality.get("largest_component_nodes"),
                "puentes": len(quality.get("bridges", [])),
                "ciclos": quality.get("cycle_basis_size"),
                "duplicados_estacion": quality.get("duplicate_stations_merged"),
                "geometrias_con_advertencia": len(quality.get("geometry_warnings", [])),
            },
            expanded=False,
        )
        with st.expander("Líneas no verificadas (motivos)"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Línea": item.get("name"),
                            "Desde": item.get("from"),
                            "Hasta": item.get("to"),
                            "Tensión": item.get("voltage_kv"),
                            "Estado": item.get("status"),
                            "Detalle": json.dumps(item.get("resolution"), ensure_ascii=False),
                        }
                        for item in quality.get("unverified_lines", [])
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        st.download_button(
            "Red completa procesada (JSON)",
            json.dumps(network, ensure_ascii=False, indent=2),
            "sein_network.json",
            "application/json",
            key="sources-network-download",
        )

    if coes:
        st.markdown("#### COES")
        st.json(
            {
                "estado": coes.get("validation_status"),
                "fecha": coes.get("probed_at_utc"),
                "urls": {
                    key: {
                        "http": value.get("http_status"),
                        "accesible": value.get("accessible"),
                        "topologia_automatica": value.get("machine_readable_topology"),
                    }
                    for key, value in coes.get("urls", {}).items()
                },
                "limitaciones": coes.get("limitations"),
            },
            expanded=False,
        )
    else:
        st.info("Sin sonda COES registrada. Ejecute `python -m scripts.download_sein --probe-coes`.")

    st.markdown("#### Limitaciones que deben acompañar cualquier resultado")
    st.markdown(
        "- La verificación es de **extremos explícitos**, no eléctrica ni COES.\n"
        "- No hay demanda, despacho, flujo AC/DC, frecuencia, protecciones ni estabilidad.\n"
        "- Una componente conectada no certifica suministro; una falla topológica no implica apagón.\n"
        "- La optimización usa demanda y pesos de escenario; los resultados no son costos oficiales.\n"
        "- Los datos de OSINERGMIN pueden cambiar; el snapshot local conserva fecha y hash.\n"
        "- QAOA se ejecuta en Aer ideal sobre instancias pequeñas; no demuestra ventaja cuántica."
    )


def render_real_page(page: str, alpha: float, beta: float, seed: int) -> None:
    if page == "Mapa eléctrico del Perú":
        render_map_page()
    elif page == "Explorador de subredes":
        render_explorer_page()
    elif page == "Red real · optimización":
        render_optimization_page(alpha, beta, seed)
    elif page == "Fuentes y metodología":
        render_sources_page()
    else:
        raise ValueError(f"Página real desconocida: {page}")
