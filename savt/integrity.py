from __future__ import annotations

import re

from savt.audit_config import AuditConfig
from savt.models import Finding

SIMILARITY_PATTERNS = [
    r"(?:similarity|similitud|coincidencia)\s*(?:index|índice|score)?\s*[:\s]*(\d{1,2}(?:\.\d+)?)\s*%",
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:overall\s*)?(?:similarity|similitud|total)",
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:match|coincidencia)",
]

AI_PATTERNS = [
    r"\bai[\s-]?generated\b",
    r"texto generado por (?:ia|inteligencia artificial|ai)",
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:ai|ia)\b",
    r"probabilidad de (?:ia|ai)\s*[:\s]*(\d{1,2}(?:\.\d+)?)\s*%",
]


def parse_similarity_from_report(text: str) -> float | None:
    if not text.strip():
        return None
    values: list[float] = []
    for pattern in SIMILARITY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                val = float(match.group(1))
                if 0 <= val <= 100:
                    values.append(val)
            except ValueError:
                continue
    if not values:
        return None
    return max(values)


def parse_ai_score_from_report(text: str) -> float | None:
    if not text.strip():
        return None
    for pattern in AI_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue
    return None


def _similarity_verdict(index: float, strict: bool) -> tuple[str, str, str]:
    warn_threshold = 10.0
    error_threshold = 15.0 if strict else 25.0
    if index < warn_threshold:
        return (
            "ok",
            "Índice de similitud dentro de rango aceptable",
            f"Similitud reportada: {index:.1f}%. Por debajo del umbral de {warn_threshold:.0f}%.",
        )
    if index < error_threshold:
        return (
            "warning",
            "Índice de similitud requiere revisión humana",
            (
                f"Similitud reportada: {index:.1f}%. Entre {warn_threshold:.0f}% y "
                f"{error_threshold:.0f}%: revisar citas, paráfrasis y bibliografía excluida del escaneo."
            ),
        )
    return (
        "error",
        "Índice de similitud elevado",
        (
            f"Similitud reportada: {index:.1f}%. Supera {error_threshold:.0f}%. "
            "Requiere revisión detallada antes de la entrega."
        ),
    )


def audit_integrity(config: AuditConfig) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    dashboard: dict = {
        "similarity_index": config.similarity_index,
        "source": "manual",
        "ai_score": None,
        "disclaimer": (
            "La similitud interna detectada por SAVT (párrafos repetidos) NO equivale a plagio externo. "
            "Para integridad académica completa, adjunte un reporte de Turnitin, iThenticate o Unicheck."
        ),
    }

    index = config.similarity_index
    report_text = config.plagiarism_report_text or ""

    if report_text.strip():
        parsed_index = parse_similarity_from_report(report_text)
        if parsed_index is not None:
            index = parsed_index
            dashboard["source"] = "reporte"
        ai_score = parse_ai_score_from_report(report_text)
        dashboard["ai_score"] = ai_score
        if ai_score is not None and ai_score >= 20:
            findings.append(
                Finding(
                    module="Integridad",
                    severity="warning",
                    title="Posible contenido generado por IA detectado en reporte",
                    detail=f"El reporte externo indica ~{ai_score:.1f}% de probabilidad de texto IA.",
                    why="Las universidades incorporan verificación de integridad académica y uso de IA.",
                    how_to_fix=(
                        "Revise con su director qué uso de IA está permitido. "
                        "Documente herramientas utilizadas y reescriba secciones señaladas."
                    ),
                )
            )

    dashboard["similarity_index"] = index

    if index is None:
        findings.append(
            Finding(
                module="Integridad",
                severity="info",
                title="Sin reporte de similitud externa",
                detail=(
                    "No se proporcionó índice de similitud ni reporte de Turnitin/iThenticate. "
                    "SAVT solo detecta repeticiones internas en el documento."
                ),
                why="La mayoría de universidades de posgrado exigen reporte de originalidad.",
                how_to_fix=(
                    "Solicite a su director escaneo en Turnitin/iThenticate y cargue el índice "
                    "en la configuración o pegue el texto del reporte."
                ),
            )
        )
        return findings, dashboard

    strict = config.profile.originality_level == "strict"
    severity, title, detail = _similarity_verdict(index, strict)
    findings.append(
        Finding(
            module="Integridad",
            severity=severity,
            title=title,
            detail=detail,
            why="El índice de similitud es estándar en evaluación de tesis a nivel global.",
            how_to_fix=(
                "Revise coincidencias señaladas, mejore paráfrasis, cite correctamente "
                "y excluya bibliografía del escaneo según normativa institucional."
            ),
        )
    )
    return findings, dashboard
