"""Mapa nacional interactivo con Plotly; no requiere token de Mapbox."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

import plotly.graph_objects as go

from ..geospatial.geometry import simplify_geometry

VOLTAGE_COLORS = {
    500.0: "#b388ff",
    220.0: "#ff5d5d",
    138.0: "#ff9f43",
    60.0: "#4bbcff",
    50.0: "#4bbcff",
    66.0: "#4bbcff",
    69.0: "#4bbcff",
    33.0: "#7f8ea3",
    30.0: "#7f8ea3",
}
DEFAULT_COLOR = "#8a94a6"
DARK = "#08111f"
PANEL = "#0c1729"


def voltage_color(value: float | None) -> str:
    if value is None:
        return DEFAULT_COLOR
    for key, color in VOLTAGE_COLORS.items():
        if abs(float(value) - key) <= 0.6:
            return color
    return DEFAULT_COLOR


def _in_filter(value: Any, allowed: set[float] | None) -> bool:
    if not allowed:
        return True
    if value is None:
        return False
    return any(abs(float(value) - item) <= 0.6 for item in allowed)


def _selected_nodes(network: dict[str, Any], departments: Iterable[str] | None, voltages: Iterable[float] | None):
    deps = {str(d).strip().upper() for d in (departments or []) if d}
    volts = {float(v) for v in (voltages or [])}
    nodes = []
    for node in network.get("nodes", []):
        if deps and str(node.get("department") or "").strip().upper() not in deps:
            continue
        node_volts = [float(v) for v in (node.get("voltages_kv") or [node.get("voltage_kv")]) if v is not None]
        if volts and not any(_in_filter(v, volts) for v in node_volts):
            continue
        nodes.append(node)
    return nodes


def _line_segments(
    network: dict[str, Any],
    node_ids: set[str],
    volts: set[float] | None,
    max_lines: int,
    tolerance: float,
) -> tuple[dict[float | None, list[dict[str, Any]]], int]:
    edges = [
        edge
        for edge in network.get("edges", [])
        if edge.get("source") in node_ids
        and edge.get("target") in node_ids
        and edge.get("validation") == "verified_endpoint_attributes"
        and (not volts or _in_filter(edge.get("voltage_kv"), volts))
    ]
    total = len(edges)
    if max_lines and total > max_lines:
        # Conserva una muestra determinista, priorizando líneas largas.
        edges = sorted(edges, key=lambda edge: (-float(edge.get("length_km") or 0), edge.get("id")))[:max_lines]
    grouped: dict[float | None, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        grouped[edge.get("voltage_kv")].append(edge)
    return grouped, total


def _flatten_lines(
    edges: list[dict[str, Any]], tolerance: float
) -> tuple[list[float | None], list[float | None], list[str]]:
    lons: list[float | None] = []
    lats: list[float | None] = []
    text: list[str] = []
    for edge in edges:
        geometry = simplify_geometry(edge.get("geometry"), tolerance)
        parts = []
        if geometry and geometry.get("type") == "LineString":
            parts = [geometry.get("coordinates") or []]
        elif geometry and geometry.get("type") == "MultiLineString":
            parts = geometry.get("coordinates") or []
        label = (
            f"{edge.get('source_name')} ↔ {edge.get('target_name')}"
            f"<br>{edge.get('voltage_kv')} kV · {edge.get('length_km')} km"
            f"<br>ID {edge.get('id')} · {edge.get('line_count', 1)} línea(s)"
            f"<br>Fuente OSINERGMIN · extremos explícitos"
        )
        for part in parts:
            for index, point in enumerate(part):
                if not point or len(point) < 2:
                    continue
                lons.append(float(point[0]))
                lats.append(float(point[1]))
                text.append(label)
            lons.append(None)
            lats.append(None)
            text.append("")
    return lons, lats, text


def peru_map(
    network: dict[str, Any],
    *,
    departments: Iterable[str] | None = None,
    voltages: Iterable[float] | None = None,
    show_lines: bool = True,
    show_stations: bool = True,
    show_generation: bool = False,
    max_lines: int = 1200,
    simplify_tolerance: float = 0.002,
    highlight_node_ids: Iterable[str] | None = None,
    highlight_edge_ids: Iterable[str] | None = None,
    show_labels: bool = False,
    height: int = 640,
) -> go.Figure:
    volts = {float(v) for v in (voltages or [])}
    nodes = _selected_nodes(network, departments, voltages)
    node_ids = {node["id"] for node in nodes}
    highlight_nodes = set(highlight_node_ids or [])
    highlight_edges = set(highlight_edge_ids or [])
    fig = go.Figure()

    shown_lines = 0
    if show_lines:
        grouped, total = _line_segments(network, node_ids, volts, max_lines, simplify_tolerance)
        for voltage, edges in sorted(grouped.items(), key=lambda item: -(item[0] or 0)):
            lons, lats, text = _flatten_lines(edges, simplify_tolerance)
            if not lons:
                continue
            shown_lines += len(edges)
            fig.add_trace(
                go.Scattergeo(
                    lon=lons,
                    lat=lats,
                    mode="lines",
                    line=dict(color=voltage_color(voltage), width=1.5),
                    name=f"L.T. {voltage:g} kV" if voltage is not None else "L.T. sin tensión",
                    legendgroup=f"line-{voltage}",
                    opacity=0.72,
                    text=text,
                    hovertemplate="%{text}<extra></extra>",
                )
            )
        if highlight_edges:
            selected = [
                edge
                for edge in network.get("edges", [])
                if str(edge.get("id")) in highlight_edges
            ]
            lons, lats, text = _flatten_lines(selected, min(simplify_tolerance, 0.0008))
            if lons:
                fig.add_trace(
                    go.Scattergeo(
                        lon=lons,
                        lat=lats,
                        mode="lines",
                        line=dict(color="#ffe08a", width=4.5),
                        name="Subred / conexión seleccionada",
                        legendgroup="highlight",
                        text=text,
                        hovertemplate="%{text}<extra></extra>",
                    )
                )

    if show_stations:
        groups: dict[float | None, list[dict[str, Any]]] = defaultdict(list)
        for node in nodes:
            groups[node.get("voltage_kv")].append(node)
        for voltage, group in sorted(groups.items(), key=lambda item: -(item[0] or 0)):
            selected = [node for node in group if node["id"] in highlight_nodes]
            normal = [node for node in group if node["id"] not in highlight_nodes]
            for subset, size, width, name in (
                (normal, 7, 1, f"SET {voltage:g} kV" if voltage is not None else "SET"),
                (selected, 13, 2.5, "Subred seleccionada"),
            ):
                if not subset:
                    continue
                fig.add_trace(
                    go.Scattergeo(
                        lon=[node["lon"] for node in subset],
                        lat=[node["lat"] for node in subset],
                        mode="markers+text" if show_labels and subset is selected else "markers",
                        text=[node["name"] for node in subset],
                        textposition="top center",
                        textfont=dict(size=9, color="#eaf7ff"),
                        marker=dict(
                            size=size,
                            color=voltage_color(voltage),
                            line=dict(color="#ffe08a" if subset is selected else "#d8f5ff", width=width),
                            symbol="circle",
                        ),
                        name=name,
                        legendgroup="stations" if subset is normal else "highlight",
                        customdata=[
                            [
                                node.get("name"),
                                node.get("department"),
                                node.get("voltage_kv"),
                                node.get("capacity_mva"),
                                node.get("id"),
                                node.get("source_ids"),
                            ]
                            for node in subset
                        ],
                        hovertemplate=(
                            "<b>%{customdata[0]}</b><br>Departamento: %{customdata[1]}"
                            "<br>Tensión: %{customdata[2]} kV<br>Capacidad: %{customdata[3]} MVA"
                            "<br>ID: %{customdata[4]}<br>Fuente: OSINERGMIN"
                            "<extra></extra>"
                        ),
                    )
                )

    if show_generation:
        gens = network.get("generation", [])
        if gens:
            fig.add_trace(
                go.Scattergeo(
                    lon=[gen["lon"] for gen in gens],
                    lat=[gen["lat"] for gen in gens],
                    mode="markers",
                    marker=dict(size=6, color="#63e6be", symbol="triangle-up", line=dict(color="#d8fff5", width=0.5)),
                    name="Generación (atributo)",
                    customdata=[
                        [gen.get("name"), gen.get("technology"), gen.get("capacity_effective_mw"), gen.get("department")]
                        for gen in gens
                    ],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>%{customdata[1]}"
                        "<br>Potencia efectiva: %{customdata[2]} MW<br>%{customdata[3]}"
                        "<extra></extra>"
                    ),
                )
            )

    fig.update_geos(
        scope="south america",
        projection_type="mercator",
        lataxis_range=[-19.5, 1.0],
        lonaxis_range=[-82.5, -68.0],
        showland=True,
        landcolor="#12233a",
        showocean=True,
        oceancolor="#07101c",
        showcountries=True,
        countrycolor="#2d4663",
        showcoastlines=True,
        coastlinecolor="#2d4663",
        showlakes=False,
        bgcolor=PANEL,
    )
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(color="#dce8f8", family="Segoe UI"),
        legend=dict(orientation="h", y=-0.02, x=0, bgcolor="rgba(8,17,31,.7)"),
        hovermode="closest",
        dragmode="pan",
        meta={
            "shown_lines": shown_lines,
            "selected_stations": len(nodes),
            "verified_only": True,
        },
    )
    return fig


def subnet_map(
    network: dict[str, Any],
    subnet: dict[str, Any],
    *,
    show_generation: bool = False,
    height: int = 560,
) -> go.Figure:
    node_ids = [node["id"] for node in subnet.get("nodes", [])]
    edge_ids = [edge["id"] for edge in subnet.get("edges", [])]
    return peru_map(
        network,
        show_lines=True,
        show_stations=True,
        show_generation=show_generation,
        max_lines=2500,
        highlight_node_ids=node_ids,
        highlight_edge_ids=edge_ids,
        show_labels=True,
        height=height,
    )
