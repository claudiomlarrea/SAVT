from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from savt import __app_name__, __version__
from savt.chapter_reviews import CHECK_LABELS
from savt.models import AuditReport
from savt.report_builder import findings_dataframe_rows
from savt.taxonomy import severity_label


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def _add_bullet(doc: Document, text: str, bold_prefix: str = "") -> None:
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        run = p.add_run(f"{bold_prefix} ")
        run.bold = True
        p.add_run(text)
    else:
        p.add_run(text)


def _add_label_paragraph(doc: Document, label: str, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(f"{label}: ")
    run.bold = True
    p.add_run(text)


def build_report_docx(report: AuditReport, dashboard: dict) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    title = doc.add_heading("Informe SAVT", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(__app_name__)
    meta = doc.add_paragraph()
    meta.add_run(f"Versión del sistema: {__version__}\n").italic = True
    meta.add_run(f"Documento analizado: {report.filename}\n").italic = True
    meta.add_run(f"Fecha del informe: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n").italic = True

    doc.add_paragraph(
        "Sistema de auditoría de tesis y trabajos finales. Diseñada para analizar "
        "la estructura, coherencia y consistencia de todos los apartados del documento, "
        "generando un informe de observaciones y recomendaciones para su mejora académica."
    )

    _add_heading(doc, "1. Síntesis (ICAI)", 1)
    _add_label_paragraph(doc, "ICAI", f"{dashboard['icai']}/100 — {dashboard['icai_interpretation']}")
    _add_label_paragraph(
        doc,
        "Estado general",
        f"{dashboard['readiness']}",
    )
    _add_label_paragraph(doc, "Motivo principal", dashboard["main_reason"])
    _add_label_paragraph(doc, "Errores críticos", str(dashboard["errors"]))
    _add_label_paragraph(doc, "Advertencias", str(dashboard["warnings"]))
    _add_label_paragraph(doc, "Páginas estimadas", str(report.page_estimate))
    _add_label_paragraph(doc, "Referencias detectadas", str(len(report.bibliography)))

    _add_heading(doc, "2. Checklist previo a la entrega", 1)
    checklist = dashboard.get("checklist", {})
    _add_label_paragraph(doc, "Estado del checklist", checklist.get("status", "—"))
    for item in checklist.get("items", []):
        mark = "Conforme" if item.get("ok") else "Requiere revisión"
        _add_bullet(doc, f"{item['label']} — {mark}")
        if not item.get("ok"):
            if item.get("summary"):
                _add_bullet(doc, item["summary"])
            for label in item.get("missing") or []:
                _add_bullet(doc, CHECK_LABELS.get(label, label), bold_prefix="•")

    _add_heading(doc, "3. Advertencias detectadas", 1)
    warnings = dashboard.get("warnings_list") or []
    if not warnings:
        doc.add_paragraph("No se registraron advertencias ni errores críticos prioritarios.")
    for idx, item in enumerate(warnings, start=1):
        _add_heading(doc, f"3.{idx} {item['title']}", 2)
        _add_label_paragraph(doc, "Gravedad", item.get("gravity", ""))
        doc.add_paragraph(item.get("detail", ""))
        if item.get("why"):
            _add_label_paragraph(doc, "Por qué importa", item["why"])
        if item.get("how_to_fix"):
            _add_label_paragraph(doc, "Cómo corregir", item["how_to_fix"])
        for row in item.get("detail_items") or []:
            line = f"{row.get('label', '')}: {row.get('value', '')}"
            if row.get("extra"):
                line += f" ({row['extra']})"
            _add_bullet(doc, line)

    _add_heading(doc, "4. Evaluación por SAVT", 1)
    jury = dashboard.get("jury", {})
    doc.add_paragraph("Fortalezas principales:")
    for idx, item in enumerate(jury.get("strengths") or ["—"], start=1):
        _add_bullet(doc, f"{idx}. {item}")
    doc.add_paragraph("Debilidades principales:")
    for idx, item in enumerate(jury.get("weaknesses") or ["—"], start=1):
        _add_bullet(doc, f"{idx}. {item}")
    _add_label_paragraph(
        doc,
        "Probabilidad estimada de aprobación",
        jury.get("approval_probability", "—"),
    )

    _add_heading(doc, "5. Revisión por capítulos", 1)
    for review in dashboard.get("chapter_reviews") or []:
        status = "Conforme" if review.get("ok") else "Requiere revisión"
        _add_heading(doc, f"{review['title']} — {status}", 2)
        doc.add_paragraph(review.get("summary", ""))
        missing = (review.get("missing") or []) + (review.get("partial_items") or [])
        if missing:
            doc.add_paragraph("Elementos a reforzar:")
            for label in missing:
                _add_bullet(doc, CHECK_LABELS.get(label, label))
        if review.get("why"):
            _add_label_paragraph(doc, "Por qué importa", review["why"])
        if review.get("how_to_fix"):
            _add_label_paragraph(doc, "Cómo corregir", review["how_to_fix"])

    _add_heading(doc, "6. Bibliografía", 1)
    bib = dashboard.get("bibliography_dashboard", {})
    lines = [
        f"Estilo: {bib.get('style', '—')}",
        f"Total referencias: {bib.get('total_refs', 0)}",
        f"Citas en texto: {bib.get('citations_found', 0)}",
        f"Citas no emparejadas: {bib.get('unmatched_citations', 0)}",
        f"Fuera del período metodológico: {bib.get('out_of_period', 0)}",
        f"Posiblemente ajenas al tema: {bib.get('possibly_off_topic', 0)}",
        f"Cobertura: {bib.get('coverage', '—')}",
    ]
    for line in lines:
        _add_bullet(doc, line)

    details = bib.get("details") or {}
    unmatched = details.get("unmatched_apa") or []
    if unmatched:
        doc.add_paragraph("Citas APA no emparejadas:")
        for entry in unmatched[:20]:
            cites = ", ".join(entry.get("citations_in_text") or [])
            _add_bullet(doc, f"{cites} (clave: {entry.get('key', '')})")

    _add_heading(doc, "7. Detalle de hallazgos", 1)
    rows = findings_dataframe_rows(report)
    if rows:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        headers = ["Área", "Severidad", "Hallazgo", "Qué significa"]
        for i, header in enumerate(headers):
            table.rows[0].cells[i].text = header
        for row in rows[:40]:
            cells = table.add_row().cells
            cells[0].text = str(row.get("Área", ""))[:40]
            cells[1].text = str(row.get("Severidad", ""))[:25]
            cells[2].text = str(row.get("Hallazgo", ""))[:120]
            cells[3].text = str(row.get("Qué significa", ""))[:200]
        if len(rows) > 40:
            doc.add_paragraph(f"(Se omitieron {len(rows) - 40} hallazgos adicionales en la tabla.)")
    else:
        doc.add_paragraph("No se registraron hallazgos adicionales.")

    doc.add_paragraph("")
    footer = doc.add_paragraph(
        "Este informe fue generado automáticamente por SAVT. "
        "No sustituye la evaluación del director de tesis ni del jurado examinador."
    )
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
