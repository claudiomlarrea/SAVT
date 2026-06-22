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
