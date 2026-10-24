"""Genera la presentación EnergyQuantum para el Qiskit Fall Fest 2026.

Salida: docs/EnergyQuantum_QFF2026.pptx
Requiere: python-pptx, Pillow y las fuentes IBM Plex Sans / IBM Plex Mono.
Los fondos de la portada y del cierre se extraen del PDF de la plantilla y se
esperan en %TEMP%/opencode/qff_imgs (p1_0_X4.png y p8_0_X4.png, p8_4_X12.png).
"""
from __future__ import annotations

import datetime
import io
import os
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "EnergyQuantum_QFF2026.pptx"
ASSETS = Path(os.environ["TEMP"]) / "opencode" / "qff_imgs"
AVATARS = Path(os.environ["TEMP"]) / "opencode" / "avatars"
AVATARS.mkdir(parents=True, exist_ok=True)
FONTS = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"

W, H = 1440, 810
PURPLE = RGBColor(0x39, 0x16, 0x6D)
PINK = RGBColor(0xFE, 0x7E, 0xB6)
CELESTE = RGBColor(0xDA, 0xE5, 0xFC)
INK = RGBColor(0x14, 0x0A, 0x2E)
MUTED = RGBColor(0x5B, 0x4F, 0x7A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLUE = RGBColor(0x00, 0x6E, 0xFF)
CARD = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xBB, 0xCC, 0xEE)
PINK_SOFT = RGBColor(0xFF, 0xF1, 0xF7)
PINK_INK = RGBColor(0x4A, 0x10, 0x30)
LAVENDER = RGBColor(0xC9, 0xB8, 0xE8)

SANS = "IBM Plex Sans"
MONO = "IBM Plex Mono"
MATH = "Cambria Math"

TEAM = [
    ("Michael Esquivel Esquivel", "Datos del SEIN", "ME", PINK, INK),
    ("Sonia Esther Chumacero Coronel", "Modelo y solvers", "SC", PURPLE, WHITE),
    ("Gabriel Izar Aaron Cornejo Quito", "QAOA y experimentos", "GC", CELESTE, INK),
    ("Jhony Cercado Atalaya", "Plataforma web", "JC", RGBColor(0, 0, 0), WHITE),
]


def avatar(initials: str, bg: RGBColor, fg: RGBColor, size: int = 420, circle: bool = True) -> Path:
    path = AVATARS / f"{initials}.png"
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = 12
    if circle:
        d.ellipse([pad, pad, size - pad, size - pad], fill=tuple(bg), outline=(255, 255, 255, 255), width=10)
    else:
        d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=28, fill=tuple(bg),
                            outline=(255, 255, 255, 255), width=10)
    font = ImageFont.truetype(str(FONTS / "IBMPlexSans-SemiBold.ttf"), int(size * 0.34))
    box = d.textbbox((0, 0), initials, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text(((size - tw) / 2 - box[0], (size - th) / 2 - box[1]), initials, font=font, fill=tuple(fg))
    img.save(path)
    return path


prs = Presentation()
prs.slide_width = Pt(W)
prs.slide_height = Pt(H)
BLANK = prs.slide_layouts[6]


def slide(bg: RGBColor = CELESTE):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = bg
    return s


def rect(s, x, y, w, h, fill=None, line=None, lw=1.0, radius=None, shape=MSO_SHAPE.RECTANGLE):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius is not None else shape
    shp = s.shapes.add_shape(kind, Pt(x), Pt(y), Pt(w), Pt(h))
    if radius is not None:
        shp.adjustments[0] = radius
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(lw)
    shp.shadow.inherit = False
    return shp


def _runs(item):
    if isinstance(item, str):
        return [(item, {})]
    if isinstance(item, tuple):
        return [item]
    return item


def text(s, x, y, w, h, runs, size=18, color=INK, font=SANS, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.12, space_after=0):
    box = s.shapes.add_textbox(Pt(x), Pt(y), Pt(w), Pt(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    if isinstance(runs, (str, tuple)):
        runs = [runs]
    elif runs and all(isinstance(r, tuple) for r in runs):
        runs = [runs]
    for i, item in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(space_after)
        for chunk, style in _runs(item):
            r = p.add_run()
            r.text = chunk
            r.font.name = style.get("font", font)
            r.font.size = Pt(style.get("size", size))
            r.font.bold = style.get("bold", bold)
            r.font.italic = style.get("italic", False)
            r.font.color.rgb = style.get("color", color)
            if "baseline" in style:
                r.font._rPr.set("baseline", str(style["baseline"]))
    return box


def sub(t, size=None):
    style = {"baseline": "-25000"}
    if size:
        style["size"] = size
    return (t, style)


def sup(t, size=None):
    style = {"baseline": "30000"}
    if size:
        style["size"] = size
    return (t, style)


def header(s, kicker, title, page):
    rect(s, 0, 0, W, 132, PURPLE)
    text(s, 108, 26, 760, 20, kicker.upper(), size=12, color=PINK, font=MONO, bold=True)
    text(s, 106, 50, 1000, 66, title, size=38, color=WHITE, bold=True)
    text(s, 1040, 54, 292, 26, "EnergyQuantum · QFF 2026", size=14, color=LAVENDER, align=PP_ALIGN.RIGHT)
    text(s, 1270, 730, 100, 46, f"{page:02d}", size=30, color=RGBColor(0x7C, 0x8F, 0xB8), align=PP_ALIGN.RIGHT)


def bullets(s, x, y, w, items, size=17, gap=16, color=INK, marker=PINK, spacing=1.18, lh=None):
    cy = y
    line_h = lh or size * spacing * 1.18
    for item in items:
        rect(s, x, cy + 8, 9, 9, marker, shape=MSO_SHAPE.DIAMOND)
        plain = "".join(c for c, _ in _runs(item))
        per_line = max(10, int(w / (size * 0.5)))
        lines = max(1, -(-len(plain) // per_line))
        text(s, x + 26, cy, w - 26, line_h * lines, item, size=size, color=color, spacing=spacing)
        cy += line_h * lines + gap
    return cy


def stat(s, x, y, w, value, label, color=PURPLE, vsize=50):
    text(s, x, y, w, vsize + 8, value, size=vsize, color=color, bold=True, spacing=0.95)
    text(s, x, y + vsize + 12, w, 40, label.upper(), size=11, color=MUTED, font=MONO, spacing=1.1)


def card(s, x, y, w, h, fill=CARD, line=LINE):
    return rect(s, x, y, w, h, fill=fill, line=line, lw=1.0, radius=0.045)


def callout(s, x, y, w, h, lines, size=17):
    rect(s, x, y, w, h, PINK_SOFT, PINK, 1.5, radius=0.06)
    rect(s, x, y, 6, h, PINK)
    text(s, x + 26, y + 14, w - 50, h - 24, lines, size=size, color=PINK_INK,
         spacing=1.2, anchor=MSO_ANCHOR.MIDDLE)


# ---------------------------------------------------------------- 1. portada
s = slide(WHITE)
s.shapes.add_picture(str(ASSETS / "p1_0_X4.png"), 0, Pt(-7.9), Pt(1440), Pt(810))
text(s, 28.8, 20, 640, 165, [
    "EnergyQuantum:",
    "grid resilience",
    "for the Qiskit Fall Fest 2026",
], size=44, color=RGBColor(0, 0, 0), font="IBM Plex Sans Light", spacing=1.02)

for i, (name, desc, ini, bg, fg) in enumerate(TEAM):
    top = 124 + i * 147.4
    text(s, 830, top, 394, 26, name, size=20, color=RGBColor(0, 0, 0), align=PP_ALIGN.RIGHT)
    text(s, 830, top + 27.5, 394, 26, desc, size=20, color=RGBColor(0, 0, 0), align=PP_ALIGN.RIGHT)
    s.shapes.add_picture(str(avatar(ini, bg, fg)), Pt(1263), Pt(top - 26), Pt(126), Pt(126))

# ---------------------------------------------------------------- 2. contexto
s = slide()
header(s, "02 — Contexto", "Una falla no se queda donde empieza", 2)
stat(s, 110, 196, 300, "685", "subestaciones en el mapa oficial")
stat(s, 430, 196, 300, "501", "conexiones con extremos verificados")
stat(s, 750, 196, 330, "153", "nodos en la mayor componente")
text(s, 110, 336, 810, 120, [
    "El mapa del SEIN que publica Osinergmin trae 685 subestaciones y 977 líneas. "
    "Al resolver los extremos de cada línea quedan 501 conexiones y una componente "
    "conectada de 153 nodos: el resto son islas sin enlace declarado.",
], size=17, color=INK, spacing=1.32)
bullets(s, 110, 462, 810, [
    "Una sola línea retirada puede partir la componente en dos.",
    "Estar conectado no significa tener suministro.",
    "Sin partición, la falla recorre toda la red que comparte enlace.",
], size=17, gap=16)
callout(s, 980, 486, 350, 170, [
    [("Cortar pocas líneas ", {}), ("fuertes", {"bold": True}), (" y dejar ", {}),
     ("dos lados parejos", {"bold": True}), (": esa es la partición que buscamos.", {})],
], size=16)

# ---------------------------------------------------------------- 3. formulación
s = slide()
header(s, "03 — Formulación", "Partición binaria: dónde cortar", 3)
card(s, 110, 190, 640, 290, fill=PURPLE, line=PURPLE)
text(s, 140, 212, 560, 24, "OBJETIVO", size=12, color=PINK, font=MONO, bold=True)
text(s, 140, 248, 580, 80, [
    [("min   H = Σ w", {}), sub("ij"), (" (1 − Z", {}), sub("i"), ("Z", {}), sub("j"), (")/2", {})],
    [("          + β (Σ d", {}), sub("i"), ("Z", {}), sub("i"), (")²", {})],
], size=25, color=WHITE, font=MATH, spacing=1.35)
text(s, 140, 386, 580, 70, [
    "QUBO → Ising con constante. 12 qubits y 2 048 particiones tras eliminar la simetría global.",
], size=13, color=LAVENDER, font=MONO, spacing=1.35)
bullets(s, 790, 200, 540, [
    [("w", {"italic": True}), sub("ij", 12), (": longitud de la conexión;   ", {}),
     ("d", {"italic": True}), sub("i", 12), (": demanda del nodo.", {})],
    "El primer término paga cada línea cortada.",
    "El segundo castiga el desbalance de demanda.",
    [("β = 3.0", {}), (" en todos los experimentos.", {})],
], size=17, gap=18)
callout(s, 790, 470, 540, 150, [
    "Los validadores van aparte de H: grupos no vacíos, conectividad y "
    "suficiencia agregada de generación.",
], size=16)
text(s, 110, 508, 640, 26, "Corte de 9 con desbalance 7: el óptimo sintético.", size=13, color=MUTED, font=MONO)

# ---------------------------------------------------------------- 4. datos
s = slide()
header(s, "04 — Datos", "De Osinergmin al grafo, sin inventar líneas", 4)
steps = [("17", "capas descargadas"), ("2 209", "registros oficiales"),
         ("685", "estaciones"), ("977", "líneas"), ("501", "conexiones")]
for i, (n, lab) in enumerate(steps):
    x = 110 + i * 250
    card(s, x, 196, 226, 130)
    text(s, x + 20, 212, 190, 46, n, size=32, color=PURPLE, bold=True)
    text(s, x + 20, 268, 190, 40, lab.upper(), size=10.5, color=MUTED, font=MONO, spacing=1.1)
    if i < 4:
        text(s, x + 226, 240, 24, 30, "›", size=26, color=PINK, bold=True, align=PP_ALIGN.CENTER)
callout(s, 110, 370, 1220, 120, [
    [("Una línea solo crea arista si ", {}), ("NODO_SALIDA", {"font": MONO, "bold": True}),
     (" y ", {}), ("NODO_LLEGADA", {"font": MONO, "bold": True}),
     (" coinciden con dos estaciones. La distancia sirve para desempatar nombres, nunca para inventar una conexión.", {})],
], size=17)
bullets(s, 110, 530, 600, [
    "618 líneas verificadas; 359 quedan fuera con el motivo registrado.",
    "Cada registro conserva capa, ID de origen y fecha.",
], size=16, gap=14)
bullets(s, 760, 530, 570, [
    "COES se consultó como sonda de acceso: 0 aristas validadas por COES.",
    "Snapshot de 17 capas disponible en data/processed.",
], size=16, gap=14)

# ---------------------------------------------------------------- 5. métodos
s = slide()
header(s, "05 — Solvers", "Cuatro métodos, el mismo contrato", 5)
methods = [
    ("Exacto", [("Enumera 2", {}), sup("n−1"), (" particiones y certifica el óptimo.", {})],
     "0.19 s · 2 047 evaluaciones", "12 nodos"),
    ("Búsqueda local", "Multirreinicio sobre vecinos 1-flip; arranca desde KL.",
     "0.07 s · 736 evaluaciones", "12 nodos"),
    ("Kernighan–Lin", "Intercambios por ganancia; no mira la demanda.",
     "0.003 s · 10 evaluaciones", "12 nodos"),
    ("QAOA", "H + RZZ + RX, p capas, COBYLA y Aer con 2 048 shots.",
     "0.87 s · 40 evaluaciones", "12 qubits"),
]
for i, (name, desc, meta, scope) in enumerate(methods):
    x = 110 + (i % 2) * 620
    y = 196 + (i // 2) * 236
    card(s, x, y, 580, 208)
    rect(s, x, y, 8, 208, PINK if i % 2 == 0 else PURPLE)
    text(s, x + 34, y + 24, 480, 34, name, size=24, color=PURPLE, bold=True)
    text(s, x + 34, y + 70, 510, 70, desc, size=16, color=INK, spacing=1.25)
    text(s, x + 34, y + 148, 400, 24, meta, size=12, color=MUTED, font=MONO)
    text(s, x + 430, y + 148, 120, 24, scope, size=12, color=PINK, font=MONO, bold=True, align=PP_ALIGN.RIGHT)
text(s, 110, 690, 1200, 26, "Los cuatro comparten la misma instancia, el mismo objetivo y la misma validación.",
     size=13, color=MUTED, font=MONO)

# ---------------------------------------------------------------- 6. sintéticos
s = slide()
header(s, "06 — Resultados sintéticos", "QAOA llega al óptimo en las 9 corridas", 6)
rect(s, 110, 196, 700, 470, WHITE, LINE, 1.0, radius=0.03)
text(s, 140, 214, 620, 24, "COSTO ESPERADO E[H] POR NÚMERO DE CAPAS", size=11, color=MUTED, font=MONO)
base_y, top_y = 590, 300
values = [(1, 0.672), (2, 0.644), (3, 0.687), (4, 0.637)]
lo, hi = 0.0, 0.80
for p, v in values:
    x = 190 + (p - 1) * 150
    hgt = (v - lo) / (hi - lo) * (base_y - top_y)
    rect(s, x, base_y - hgt, 86, hgt, CELESTE, PURPLE, 1.0)
    text(s, x - 10, base_y - hgt - 30, 106, 22, f"{v:.3f}", size=14, color=PURPLE, bold=True, align=PP_ALIGN.CENTER)
    text(s, x - 10, base_y + 14, 106, 22, f"p = {p}", size=13, color=INK, font=MONO, align=PP_ALIGN.CENTER)
opt_y = base_y - (0.22524 - lo) / (hi - lo) * (base_y - top_y)
rect(s, 150, opt_y, 620, 2, PINK)
rect(s, 556, 223, 26, 2, PINK)
text(s, 590, 214, 190, 22, "H* = 0.22524", size=11, color=PINK, font=MONO, bold=True, align=PP_ALIGN.RIGHT)
text(s, 150, base_y + 48, 620, 22, "3 semillas por capa · 2 048 shots · Aer ideal", size=12, color=MUTED, font=MONO)
stat(s, 860, 200, 480, "9 / 9", "corridas que alcanzaron el óptimo exacto", PURPLE, 46)
stat(s, 860, 320, 480, "0.4 %", "probabilidad de medir el óptimo", PINK, 46)
stat(s, 860, 440, 480, "0.44 → 0.87 s", "tiempo por corrida, de p=1 a p=4", PURPLE, 40)
text(s, 860, 570, 480, 110, [
    "E[H] baja de 0.672 a 0.637. La referencia uniforme con los mismos shots también "
    "alcanza el óptimo: no hay ventaja cuántica.",
], size=13, color=MUTED, font=MONO, spacing=1.35)

# ---------------------------------------------------------------- 7. red real
s = slide()
header(s, "07 — Red real", "Trujillo: 6 nodos del SEIN verificado", 7)
for i, (n, lab) in enumerate([("6", "nodos"), ("6", "conexiones"), ("51.03", "km totales"), ("1", "componente")]):
    stat(s, 110 + i * 175, 190, 165, n, lab, PURPLE, 38)
text(s, 110, 282, 660, 24, "60 / 138 / 220 / 500 kV · 2 puentes · 1 ciclo base", size=12, color=MUTED, font=MONO)
rows = [("Exacto", "0.2322", "11.85", "0.003 s"),
        ("Búsqueda local", "0.2322", "11.85", "0.019 s"),
        ("Kernighan–Lin", "0.2322", "11.85", "0.002 s"),
        ("QAOA (p=1)", "0.2322", "11.85", "0.19 s")]
cols = [110, 330, 520, 650]
for j, hd in enumerate(["MÉTODO", "H", "CORTE", "TIEMPO"]):
    text(s, cols[j], 336, 200, 22, hd, size=10.5, color=MUTED, font=MONO, bold=True)
for i, row in enumerate(rows):
    y = 384 + i * 56
    if i % 2 == 0:
        rect(s, 110, y - 6, 660, 48, WHITE)
    for j, val in enumerate(row):
        text(s, cols[j], y, 200, 24, val, size=15, color=INK if j else PURPLE,
             bold=(j == 0), font=SANS if j == 0 else MONO)
text(s, 110, 604, 660, 60, "Los cuatro métodos llegan al mismo H. La instancia es demasiado chica para distinguirlos.",
     size=13, color=MUTED, font=MONO, spacing=1.35)
card(s, 820, 190, 510, 400)
text(s, 850, 212, 450, 24, "FALLA DE PRUEBA", size=11, color=PINK, font=MONO, bold=True)
text(s, 850, 244, 450, 60, "Se retira el puente HUACA DEL SOL ↔ TRUJILLO SUR (6.21 km).",
     size=17, color=INK, spacing=1.3)
for i, (v, lab) in enumerate([("1 → 2", "componentes"), ("6 → 5", "conexiones activas"),
                              ("0 → 1", "nodo aislado")]):
    text(s, 850, 330 + i * 66, 200, 34, v, size=28, color=PURPLE, bold=True)
    text(s, 1030, 342 + i * 66, 270, 26, lab.upper(), size=11, color=MUTED, font=MONO)
callout(s, 820, 616, 510, 84, [
    "La falla es topológica: no estimamos energía no suministrada.",
], size=14)

# ---------------------------------------------------------------- 8. plataforma
s = slide()
header(s, "08 — Plataforma", "Los resultados, navegables", 8)
pic = ROOT / "docs" / "captures" / "landing-escritorio.png"
s.shapes.add_picture(str(pic), Pt(110), Pt(200), Pt(760), Pt(428))
rect(s, 110, 200, 760, 428, None, PURPLE, 1.0)
bullets(s, 910, 205, 430, [
    "Streamlit: 12 pantallas, 8 sintéticas y 4 de datos reales.",
    "API FastAPI: red, subredes, optimización y fallas.",
    "Frontend React + MapLibre en localhost:3001.",
    "Exporta JSON, CSV y GraphML con procedencia.",
    "Todo local: sin credenciales ni hardware de IBM.",
], size=15, gap=16)
callout(s, 110, 660, 760, 80, [
    [("Un comando y semillas fijas: ", {}), ("python -m scripts.run_real_experiment", {"font": MONO, "bold": True})],
], size=14)

# ---------------------------------------------------------------- 9. honestidad
s = slide()
header(s, "09 — Lectura honesta", "Hoy gana lo clásico. Lo decimos.", 9)
rows = [("Exacto", "0.2252", "9", "Sí", "0.19 s"),
        ("Búsqueda local", "0.2252", "9", "Sí", "0.07 s"),
        ("Kernighan–Lin", "0.2252", "9", "Sí", "0.003 s"),
        ("QAOA p=4", "0.2252", "9", "Sí", "0.87 s")]
cols = [110, 420, 620, 780, 960]
for j, hd in enumerate(["MÉTODO", "H", "CORTE", "¿ÓPTIMO?", "TIEMPO"]):
    text(s, cols[j], 196, 220, 22, hd, size=11, color=MUTED, font=MONO, bold=True)
for i, row in enumerate(rows):
    y = 232 + i * 58
    if i % 2 == 0:
        rect(s, 110, y - 8, 1070, 50, WHITE)
    for j, val in enumerate(row):
        text(s, cols[j], y, 240, 26, val, size=17, color=INK if j else PURPLE,
             bold=(j == 0), font=SANS if j == 0 else MONO)
callout(s, 110, 490, 580, 130, [
    [("KL no mira la demanda. ", {"bold": True}),
     ("Falla en 6 y 8 nodos: 0.5685 y 0.4981 frente a 0.3210 y 0.2664 del óptimo.", {})],
], size=15)
callout(s, 720, 490, 610, 130, [
    [("Con 100 nodos hay 2", {"bold": True}), sup("99", 12),
     (" particiones. ", {"bold": True}),
     ("Ahí los atajos clásicos dejan de garantizar el óptimo.", {})],
], size=15)
text(s, 110, 655, 1220, 60, [
    [("Nuestro aporte: ", {}), ("formulación completa y validada", {"bold": True}),
     (" a una escala donde cada resultado se puede comprobar contra el exacto.", {})],
], size=16, color=INK)

# ---------------------------------------------------------------- 10. límites
s = slide()
header(s, "10 — Límites", "Lo que este trabajo no afirma", 10)
cols = [(110, "LÍMITES", [
            "12 nodos como máximo; la mayor componente real tiene 153.",
            "Aer ideal, sin ruido ni chip real de IBM.",
            "Demanda y generación son supuestos, no despacho oficial.",
        ]),
        (560, "TAMPOCO MODELAMOS", [
            "Flujo AC/DC, protecciones, frecuencia ni energía no suministrada.",
            "Más de dos grupos o restricciones eléctricas dentro de H.",
            "Validación automática de COES: las 501 aristas tienen coes_validated = false.",
        ]),
        (1010, "SIGUIENTES PASOS", [
            "Chip real de IBM con mitigación de errores.",
            "Subir a 20–30 nodos con heurísticas híbridas.",
            "Restricciones de capacidad y flujo en el Hamiltoniano.",
        ])]
for x, label, items in cols:
    text(s, x, 186, 380, 22, label, size=11, color=PINK, font=MONO, bold=True)
    bullets(s, x, 220, 380, items, size=15, gap=16)
callout(s, 110, 490, 1220, 120, [
    [("Una conexión verificada solo dice que los extremos declarados coinciden. ", {}),
     ("No certifica suministro ni operación.", {"bold": True})],
], size=17)
text(s, 110, 690, 1220, 26, "docs/LIMITATIONS.md · docs/TOPOLOGY_VALIDATION.md", size=12, color=MUTED, font=MONO)

# ---------------------------------------------------------------- 11. cierre
s = slide(WHITE)
s.shapes.add_picture(str(ASSETS / "p8_0_X4.png"), Pt(-3.2), Pt(-7.9), Pt(1446.7), Pt(810))
s.shapes.add_picture(str(ASSETS / "p8_4_X12.png"), Pt(22.6), Pt(728.9), Pt(234), Pt(56.2))
text(s, 0, 155, W, 80, "IBM QUANTUM", size=64, color=BLUE, font="IBM Plex Sans Light",
     align=PP_ALIGN.CENTER, spacing=1.0)
text(s, 0, 243, W, 80, "GLOBAL HACKATHON", size=64, color=BLUE, font="IBM Plex Sans Light",
     align=PP_ALIGN.CENTER, spacing=1.0)
text(s, 0, 400, W, 36, "TEAM ENERGYQUANTUM", size=30, color=BLUE, font=SANS, align=PP_ALIGN.CENTER)
for i, (name, desc, ini, bg, fg) in enumerate(TEAM):
    s.shapes.add_picture(str(avatar(ini, bg, fg, circle=False)), Pt(386.5 + i * 181), Pt(477), Pt(124), Pt(124))
text(s, 0, 700, W, 26, "github.com/cercadoUE/EnergyQuantum", size=14, color=RGBColor(0x8A, 0x8A, 0x8A),
     font=MONO, align=PP_ALIGN.CENTER)

now = datetime.datetime.now().replace(microsecond=0)
prs.core_properties.title = "EnergyQuantum - Qiskit Fall Fest 2026"
prs.core_properties.author = "EnergyQuantum"
prs.core_properties.last_modified_by = "EnergyQuantum"
prs.core_properties.subject = "Partición binaria de la red eléctrica del Perú"
prs.core_properties.comments = ""
prs.core_properties.keywords = "Qiskit, QAOA, SEIN, Osinergmin"
prs.core_properties.created = now
prs.core_properties.modified = now
prs.core_properties.revision = 1
OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)


def _fix_package(path: Path, slides: int) -> None:
    """Corrige los metadatos que python-pptx hereda de su plantilla en blanco."""
    cover = Image.open(ASSETS / "p1_0_X4.png").convert("RGB")
    cover.thumbnail((512, 512))
    thumb = io.BytesIO()
    cover.save(thumb, "JPEG", quality=88)

    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename == "docProps/thumbnail.jpeg":
                dst.writestr(item, thumb.getvalue())
                continue
            data = src.read(item.filename)
            if item.filename == "docProps/app.xml":
                txt = data.decode("utf-8")
                txt = txt.replace("Microsoft Macintosh PowerPoint", "Microsoft Office PowerPoint")
                txt = re.sub(r"<Slides>\d+</Slides>", f"<Slides>{slides}</Slides>", txt)
                txt = re.sub(r"<PresentationFormat>.*?</PresentationFormat>",
                             "<PresentationFormat>Widescreen</PresentationFormat>", txt)
                data = txt.encode("utf-8")
            dst.writestr(item, data)
    tmp.replace(path)


_fix_package(OUT, len(prs.slides._sldIdLst))
print("OK", OUT, OUT.stat().st_size)
