"""Etiquetas de conformidad para la interfaz institucional SAVT."""

from __future__ import annotations


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
