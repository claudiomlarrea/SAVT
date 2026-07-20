"""Etiquetas de conformidad para la interfaz institucional SAVT."""

from __future__ import annotations

CONFORMANCE_COLORS = {
    "Conforme": "#15803d",
    "Parcialmente conforme": "#ca8a04",
    "No conforme": "#b91c1c",
}


def conformance_label(ok: bool, partial: bool = False) -> str:
    if ok:
        return "Conforme"
    if partial:
        return "Parcialmente conforme"
    return "No conforme"


def readiness_conformance_label(status: str) -> str:
    return {
        "Lista para presentar": "Conforme",
        "Apta con correcciones menores": "Parcialmente conforme",
        "Requiere revisión antes de presentar": "Parcialmente conforme",
        "No apta para presentar": "No conforme",
        "No apta para presentación": "No conforme",
    }.get(status, "Parcialmente conforme")


def conformance_from_review(ok: bool | None, partial: bool = False) -> str:
    if ok is True:
        return "Conforme"
    if partial:
        return "Parcialmente conforme"
    if ok is False:
        return "No conforme"
    return "—"


def depth_status_from_review(ok: bool | None, partial: bool = False) -> str:
    if ok is True:
        return "adequate"
    if partial:
        return "partial"
    if ok is False:
        return "weak"
    return "missing"


def conformance_badge(ok: bool, partial: bool = False) -> str:
    return conformance_badge_from_label(conformance_label(ok, partial))


def conformance_badge_from_label(label: str) -> str:
    color = CONFORMANCE_COLORS.get(label, CONFORMANCE_COLORS["Parcialmente conforme"])
    return (
        f'<span style="color:{color};font-weight:700;">{label}</span>'
    )


def readiness_conformance_badge(status: str) -> str:
    return conformance_badge_from_label(readiness_conformance_label(status))


def citation_style_label(style: str | None) -> str:
    if not style or style == "—":
        return "—"
    normalized = style.strip().lower()
    if normalized in ("numbered", "numeric", "vancouver"):
        return "Vancouver"
    if normalized == "apa":
        return "APA"
    return style.upper()


def citation_reading_summary(recon: dict, *, total_refs: int | None = None) -> str:
    """Texto breve para jurados: fuentes únicas vs apariciones vs bibliografía."""
    appearances = int(recon.get("body_occurrences") or 0)
    text_unique = int(recon.get("text_unique_raw") or recon.get("document_unique_cited") or 0)
    bib_used = int(recon.get("document_unique_cited") or 0)
    total = int(total_refs if total_refs is not None else recon.get("total_references") or 0)
    uncited = int(recon.get("uncited_references") or 0)
    if total and uncited > total:
        uncited = max(0, total - bib_used)
    unmatched = int(recon.get("unmatched_citations") or 0)
    style = str(recon.get("style") or "").lower()
    if style in {"numbered", "numeric", "vancouver"}:
        style_name = "Vancouver (numerado)"
        unique_label = "números de referencia distintos"
    else:
        style_name = "APA (autor-año)"
        unique_label = "fuentes autor-año distintas"
    tail = (
        f"; **{unmatched}** cita(s) en el texto sin entrada bibliográfica clara."
        if unmatched
        else "."
    )
    return (
        f"Estilo detectado: **{style_name}**. "
        f"**{text_unique}** {unique_label} en el cuerpo "
        f"(**{appearances}** apariciones si se repiten). "
        f"En la bibliografía final (**{total}** entradas), **{bib_used}** están citadas al menos una vez "
        f"y **{uncited}** no aparecen en el texto{tail}"
    )
