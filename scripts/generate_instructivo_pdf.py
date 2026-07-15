#!/usr/bin/env python3
"""Genera el instructivo PDF de SAVT — misma estética Observatorio/EvaluAR."""

from __future__ import annotations

import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "instructivo"
LOGO = ROOT / "assets" / "logo_observatorio_ia.png"
OUTPUT = ROOT / "assets" / "instructivo_savt.pdf"
DOCS_OUTPUT = Path.home() / "Documents" / "SAVT" / "instructivo-savt-uccuyo.pdf"
OBS_OUTPUT = (
    Path.home()
    / "Projects"
    / "observatorio-ia"
    / "docs"
    / "instructivos"
    / "instructivo-savt.pdf"
)

URL_UCCUYO = "https://uccuyo.edu.ar/"
URL_OBS = "https://claudiomlarrea.github.io/observatorio-ia/"
URL_HERR = "https://claudiomlarrea.github.io/observatorio-ia/#herramientas"
URL_APP = "https://8j4mtw4waqxwme7cm5eaeq.streamlit.app/?src=observatorio"
URL_MAIL = "observatorioia@uccuyo.edu.ar"

GREEN = colors.HexColor("#044A30")
GREEN_BANNER = colors.HexColor("#064a38")
MAROON = colors.HexColor("#7a1532")
MAROON_DARK = colors.HexColor("#4a0c1f")
GRAY = colors.HexColor("#64748b")
TEXT = colors.HexColor("#1e293b")
WHITE = colors.white


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=26,
            textColor=WHITE,
            spaceAfter=12,
            alignment=TA_CENTER,
            leading=32,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            parent=base["Normal"],
            fontSize=13,
            textColor=WHITE,
            alignment=TA_CENTER,
            spaceAfter=10,
            leading=18,
        ),
        "cover_muted": ParagraphStyle(
            "cover_muted",
            parent=base["Normal"],
            fontSize=11,
            textColor=colors.Color(1, 1, 1, alpha=0.9),
            alignment=TA_CENTER,
            spaceAfter=8,
            leading=16,
        ),
        "cover_body": ParagraphStyle(
            "cover_body",
            parent=base["Normal"],
            fontSize=10.5,
            textColor=colors.Color(1, 1, 1, alpha=0.92),
            alignment=TA_CENTER,
            spaceAfter=6,
            leading=15,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=GREEN,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=MAROON_DARK,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=TEXT,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=14,
            spaceAfter=4,
        ),
        "url": ParagraphStyle(
            "url",
            parent=base["Normal"],
            fontSize=9,
            textColor=GREEN,
            spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontSize=8.5,
            textColor=GRAY,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "step": ParagraphStyle(
            "step",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=MAROON_DARK,
            spaceBefore=8,
            spaceAfter=4,
        ),
    }


def _p(text: str, style: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(text, styles[style])


def _bullets(items: list[str], styles: dict[str, ParagraphStyle]) -> list:
    return [_p(f"• {item}", "bullet", styles) for item in items]


def _image(path: Path, width: float = 165 * mm, max_height: float = 95 * mm) -> Image | Spacer:
    if not path.is_file():
        return Spacer(1, 6)
    reader = ImageReader(str(path))
    iw, ih = reader.getSize()
    if iw <= 0 or ih <= 0:
        return Spacer(1, 6)
    height = width * (ih / iw)
    if height > max_height:
        height = max_height
        width = height * (iw / ih)
    img = Image(str(path), width=width, height=height)
    img.hAlign = "CENTER"
    return img


def _url_block(label: str, url: str, styles: dict[str, ParagraphStyle]) -> list:
    return [
        _p(f"<b>{label}</b>", "body", styles),
        _p(f'<link href="{url}"><u>{url}</u></link>', "url", styles),
        Spacer(1, 4),
    ]


def _section(title: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return _p(title, "h1", styles)


def build_story(styles: dict[str, ParagraphStyle]) -> list:
    story: list = []

    story.append(Spacer(1, 48 * mm))
    if LOGO.is_file():
        logo = Image(str(LOGO), width=36 * mm, height=36 * mm)
        logo.hAlign = "CENTER"
        story += [logo, Spacer(1, 10 * mm)]
    story += [
        _p("UNIVERSIDAD CATÓLICA DE CUYO", "cover_muted", styles),
        _p("Observatorio de Inteligencia Artificial", "cover_subtitle", styles),
        Spacer(1, 8 * mm),
        _p("Instructivo SAVT", "cover_title", styles),
        _p("Auditoría de Tesis · Pre-revisión académica integral", "cover_subtitle", styles),
        Spacer(1, 14 * mm),
        _p(
            "Guía paso a paso para tesistas, directores e investigadores:<br/>"
            "acceso, carga del documento, configuración, lectura del ICAI<br/>"
            "y descarga del informe en CSV, Excel o Word.",
            "cover_body",
            styles,
        ),
        Spacer(1, 28 * mm),
        _p(URL_MAIL, "cover_muted", styles),
        PageBreak(),
    ]

    story.append(_section("Índice", styles))
    toc = [
        "1. ¿Qué es SAVT?",
        "2. Cómo acceder desde la web de la UCCuyo",
        "3. Pantalla de inicio y barra lateral",
        "4. Qué documento subir",
        "5. Ejecutar la auditoría",
        "6. Interpretar el ICAI y el checklist",
        "7. Apartados, bibliografía, integridad y ética",
        "8. Descargar el informe",
        "9. Valoración del sistema",
        "10. Consejos útiles",
        "11. URLs de referencia",
    ]
    story += [_p(line, "bullet", styles) for line in toc]
    story.append(PageBreak())

    story.append(_section("1. ¿Qué es SAVT?", styles))
    story += _bullets(
        [
            "<b>SAVT</b> = Sistema de Auditoría y Verificación de Tesis (v0.5.2).",
            "Herramienta del Observatorio de IA (UCCuyo) para la "
            "<b>pre-auditoría académica</b> de tesis y trabajos finales.",
            "Revisa estructura, coherencia, bibliografía/citas, integridad, ética y profundidad "
            "<b>antes</b> de la evaluación del jurado.",
            "Cada hallazgo indica qué significa, por qué importa y cómo corregirlo.",
            "<b>No sustituye</b> al director ni al jurado: es una guía orientativa.",
            "Entrega un índice <b>ICAI</b> (0–100) de preparación global para presentar.",
        ],
        styles,
    )
    story.append(_p("Escala ICAI", "h2", styles))
    story += _bullets(
        [
            "90–100: Excelente",
            "80–89: Muy buena",
            "70–79: Apta con ajustes menores",
            "60–69: Requiere revisión",
            "Menos de 60: No apta para presentación",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("2. Cómo acceder desde la web de la UCCuyo", styles))
    story.append(
        _p(
            "Podés entrar directo con el enlace del paso 4, o por la ruta institucional:",
            "body",
            styles,
        )
    )
    for title, url, img, desc in [
        (
            "Paso 1 — Sitio de la Universidad",
            URL_UCCUYO,
            "01-uccuyo.jpg",
            "Ingresá a la UCCuyo. En Accesos o el menú, buscá "
            "<b>Observatorio de Inteligencia Artificial</b>.",
        ),
        (
            "Paso 2 — Observatorio de IA",
            URL_OBS,
            "02-observatorio-inicio.jpg",
            "Usá el menú o el botón <b>Herramientas de análisis</b>.",
        ),
        (
            "Paso 3 — Herramientas de análisis",
            URL_HERR,
            "03-herramientas-savt.jpg",
            "En la tarjeta <b>SAVT — Auditoría de Tesis</b> hacé clic en "
            "<b>Abrir SAVT</b> (también podrás bajar este instructivo en PDF).",
        ),
        (
            "Paso 4 — SAVT",
            URL_APP,
            "04-savt-inicio.jpg",
            "Si la app estaba dormida (Streamlit), tocá "
            "<b>Yes, get this app back up!</b> y esperá unos segundos.",
        ),
    ]:
        story.append(_p(title, "step", styles))
        story += _url_block("URL:", url, styles)
        story.append(_p(desc, "body", styles))
        story.append(_image(ASSETS / img))
        story.append(_p(f"Figura: {title}", "caption", styles))
    story.append(PageBreak())

    story.append(_section("3. Pantalla de inicio y barra lateral", styles))
    story.append(_p("Inicio", "h2", styles))
    story += _bullets(
        [
            "Uploader: <b>Subir tesis (.docx o .pdf)</b>.",
            "Mensaje de bienvenida con tip: elegir perfil en la barra lateral.",
            "Sección <b>Valoración del sistema</b> (disponible también sin auditoría).",
        ],
        styles,
    )
    story.append(_p("Barra lateral — Configuración", "h2", styles))
    story += _bullets(
        [
            "<b>Nivel de titulación:</b> Auto · Grado (TFG/TFI) · Especialización · "
            "Maestría académica · Maestría profesional · Doctorado.",
            "<b>Verificar DOI online (Crossref)</b> y máximo de DOI a verificar.",
            "Páginas mínimas / máximas objetivo.",
            "<b>Integridad académica:</b> opcional incluir índice de similitud "
            "(Turnitin / iThenticate) y pegar texto del reporte.",
            "<b>Módulos de auditoría:</b> Normativa institucional · Ética · "
            "Originalidad y aporte · Profundidad académica.",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("4. Qué documento subir", styles))
    story += _bullets(
        [
            "Formatos: <b>.docx</b> o <b>.pdf</b> (preferible PDF exportado desde Word).",
            "Tamaño máximo típico en Cloud: ~200 MB.",
            "Conviene un documento con índice e encabezados claros.",
            "Privacidad: el archivo vive en la sesión del navegador; no queda "
            "guardado en el repositorio público.",
            "No subas datos personales sensibles sin autorización.",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("5. Ejecutar la auditoría", styles))
    story += _bullets(
        [
            "Elegí el nivel de titulación (o dejá Auto).",
            "Ajustá DOI, páginas y módulos si hace falta.",
            "(Opcional) Activá el índice de similitud externo o pegá el reporte.",
            "Subí el archivo.",
            "Pulsá <b>Ejecutar auditoría</b>.",
            "Verás progreso: detección de apartados, estructura, profundidad, "
            "bibliografía y citas, informe final.",
            "Al terminar: <b>Auditoría completada</b> y se muestra el resultado.",
            "Si falla: Manage app → Reboot en Streamlit Cloud y reintentá.",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("6. Interpretar el ICAI y el checklist", styles))
    story += _bullets(
        [
            "<b>Resultado general (ICAI)</b>: puntuación /100 e interpretación.",
            "<b>Estado general:</b> Lista para presentar · Apta con correcciones menores · "
            "Requiere revisión · No apta para presentar.",
            "Badges: Conforme / Parcialmente conforme / No conforme.",
            "<b>Checklist de presentación:</b> resumen ejecutivo por capítulo "
            "(Introducción, Objetivos, Marco, Metodología, Resultados, Discusión, "
            "Conclusiones, Bibliografía).",
            "El detalle accionable está en <b>Apartados con observaciones</b>.",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("7. Apartados, bibliografía, integridad y ética", styles))
    story += _bullets(
        [
            "<b>Apartados con observaciones:</b> qué falta, por qué importa, cómo corregir.",
            "<b>Bibliografía y citación:</b> estilo, citas no emparejadas, DOI, "
            "referencias fuera de período o ajenas al tema; figuras y tablas.",
            "<b>Integridad académica:</b> similitud interna ≠ plagio externo; "
            "usar Turnitin/iThenticate si corresponde.",
            "<b>Ética de investigación:</b> consentimiento, comité, confidencialidad, etc.",
            "<b>Originalidad y aporte</b> y <b>Hallazgos críticos</b> priorizados.",
            "<b>Evaluación orientativa por SAVT:</b> fortalezas, debilidades y "
            "probabilidad estimada de aprobación (heurística; no es dictamen oficial).",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("8. Descargar el informe", styles))
    story += _bullets(
        [
            "Sección <b>Informe final SAVT</b>.",
            "<b>Descargar CSV (hallazgos)</b>",
            "<b>Descargar Excel (.xlsx)</b>",
            "<b>Descargar Word (.docx)</b>",
            "Podés filtrar por severidad y áreas (estructura, bibliografía, ética, etc.).",
            "Guardá el informe en tu computadora: es tu respaldo de la pre-auditoría.",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("9. Valoración del sistema", styles))
    story += _bullets(
        [
            "Al final (o sin auditar): <b>Valoración del sistema</b>.",
            "Calificación general + opinión opcional → <b>Enviar valoración</b>.",
            "Ayuda a mejorar SAVT para la comunidad UCCuyo.",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("10. Consejos útiles", styles))
    story += _bullets(
        [
            "Preferí Word bien armado o PDF exportado desde Word.",
            "Activá Crossref para DOI; bajá el máximo si la red es lenta.",
            "Tras cambiar el archivo, volvé a pulsar <b>Ejecutar auditoría</b>.",
            "Si la app dormida aparece, despertála y esperá 30–60 s.",
            "Las páginas en Word se estiman; en PDF suelen ser más fiables.",
            "SAVT no reemplaza la evaluación humana ni un software antiplagio externo.",
            f"Consultas: {URL_MAIL}",
        ],
        styles,
    )
    story.append(PageBreak())

    story.append(_section("11. URLs de referencia", styles))
    for label, url in [
        ("Universidad Católica de Cuyo", URL_UCCUYO),
        ("Observatorio de IA", URL_OBS),
        ("Herramientas de análisis", URL_HERR),
        ("SAVT (acceso directo)", URL_APP),
        (f"Correo: {URL_MAIL}", f"mailto:{URL_MAIL}"),
    ]:
        story += _url_block(label, url, styles)

    story += [
        Spacer(1, 20),
        _p(
            "SAVT · Observatorio de Inteligencia Artificial · Universidad Católica de Cuyo",
            "caption",
            styles,
        ),
    ]
    return story


def _draw_cover_background(canvas, doc) -> None:
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(MAROON)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setFillColor(MAROON_DARK)
    canvas.setFillAlpha(0.35)
    canvas.rect(w * 0.55, 0, w * 0.45, h, fill=1, stroke=0)
    canvas.setFillAlpha(1)
    canvas.setFillColor(GREEN_BANNER)
    canvas.rect(0, h - 14 * mm, w, 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(
        w / 2,
        h - 9 * mm,
        "UNIVERSIDAD CATÓLICA DE CUYO  ·  OBSERVATORIO DE INTELIGENCIA ARTIFICIAL",
    )
    canvas.setFillColor(GREEN_BANNER)
    canvas.rect(0, 0, w, 6 * mm, fill=1, stroke=0)
    canvas.restoreState()


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(20 * mm, 12 * mm, "SAVT · Instructivo UCCuyo · Observatorio de IA")
    canvas.drawRightString(190 * mm, 12 * mm, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def _first_page(canvas, doc) -> None:
    _draw_cover_background(canvas, doc)


def main() -> None:
    styles = _styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OBS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="Instructivo SAVT — Auditoría de Tesis",
        author="Observatorio de Inteligencia Artificial - UCCuyo",
    )
    doc.build(build_story(styles), onFirstPage=_first_page, onLaterPages=_header_footer)

    shutil.copy2(OUTPUT, DOCS_OUTPUT)
    if OBS_OUTPUT.parent.is_dir():
        shutil.copy2(OUTPUT, OBS_OUTPUT)
    print(f"Generado: {OUTPUT}")
    print(f"Copia:    {DOCS_OUTPUT}")
    if OBS_OUTPUT.is_file():
        print(f"Obs:      {OBS_OUTPUT}")


if __name__ == "__main__":
    main()
