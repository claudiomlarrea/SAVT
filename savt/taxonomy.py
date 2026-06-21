from __future__ import annotations

MODULE_TO_AREA: dict[str, str] = {
    "Bibliografía": "Bibliografía",
    "Referencias": "Bibliografía",
    "Coherencia": "Coherencia",
    "Pregunta de investigación": "Coherencia",
    "Objetivos": "Coherencia",
    "Figuras": "Figuras y tablas",
    "Tablas": "Figuras y tablas",
    "Estilo": "Redacción",
    "Extensión": "Estructura",
    "Estructura": "Estructura",
    "Metodología": "Metodología",
    "Conclusiones": "Conclusiones",
    "Citas": "Citas",
    "Similitud": "Integridad",
    "Integridad": "Integridad",
    "Ética": "Ética",
    "Originalidad": "Originalidad",
    "Normativa": "Normativa institucional",
    "Contenido": "Profundidad académica",
    "Evaluación": "Coherencia",
}

SEVERITY_LABELS: dict[str, str] = {
    "error": "Errores críticos",
    "warning": "Advertencias",
    "info": "Recomendaciones",
    "ok": "Aspectos conformes",
}

AUDIT_AREAS: list[str] = [
    "Estructura",
    "Metodología",
    "Coherencia",
    "Bibliografía",
    "Citas",
    "Figuras y tablas",
    "Redacción",
    "Conclusiones",
    "Normativa institucional",
    "Integridad",
    "Ética",
    "Originalidad",
    "Profundidad académica",
]

GUIDANCE: dict[str, dict[str, str]] = {
    "Respuesta a la pregunta de investigación poco explícita": {
        "why": "Un evaluador espera que las conclusiones cierren el ciclo argumental iniciado en la introducción.",
        "how_to_fix": "Agregue un párrafo inicial en conclusiones que responda explícitamente la pregunta con los hallazgos principales.",
    },
    "Citas APA sin coincidencia exacta en bibliografía": {
        "why": "Las citas sin entrada bibliográfica debilitan la trazabilidad académica del trabajo.",
        "how_to_fix": "Revise cada cita señalada y complete la referencia en bibliografía o corrija el autor/año en el texto.",
    },
    "Referencias bibliográficas no citadas": {
        "why": "Incluir referencias no utilizadas sugiere bibliografía inflada o citas faltantes.",
        "how_to_fix": "Elimine referencias no citadas o incorpórelas donde correspondan en el desarrollo.",
    },
    "Posible desajuste cita ↔ contenido del párrafo": {
        "why": "Una cita mal ubicada puede interpretarse como error metodológico o de revisión.",
        "how_to_fix": "Verifique que cada referencia citada respalde la afirmación del párrafo donde aparece.",
    },
    "Figuras no citadas en el cuerpo del texto": {
        "why": "Toda figura debe integrarse al argumento; una figura huérfana queda fuera del análisis.",
        "how_to_fix": "Mencione cada figura en el texto antes o al presentarla (p. ej. 'Como se observa en la Figura 2…').",
    },
    "Extensión por debajo del rango objetivo": {
        "why": "Un trabajo demasiado breve puede no desarrollar suficientemente el marco o la discusión.",
        "how_to_fix": "Amplíe marco teórico, discusión o conclusiones según indicaciones de su director.",
    },
    "No se detectó pregunta de investigación": {
        "why": "La pregunta orienta objetivos, metodología y conclusiones.",
        "how_to_fix": "Formule una pregunta explícita en la introducción, idealmente en una sección dedicada.",
    },
}


def area_for_module(module: str) -> str:
    return MODULE_TO_AREA.get(module, module)


def severity_label(severity: str) -> str:
    return SEVERITY_LABELS.get(severity, severity)


def enrich_finding(finding) -> None:
    from savt.models import Finding

    if not isinstance(finding, Finding):
        return
    if not finding.area:
        finding.area = area_for_module(finding.module)
    guidance = GUIDANCE.get(finding.title, {})
    if not finding.why and guidance.get("why"):
        finding.why = guidance["why"]
    if not finding.how_to_fix and guidance.get("how_to_fix"):
        finding.how_to_fix = guidance["how_to_fix"]


def icao_interpretation(score: int) -> str:
    if score >= 90:
        return "Excelente"
    if score >= 80:
        return "Muy buena"
    if score >= 70:
        return "Apta con ajustes menores"
    if score >= 60:
        return "Requiere revisión"
    return "No apta para presentación"


def presentation_status(score: int, errors: int, warnings: int) -> tuple[str, str, str]:
    from savt.ui_labels import readiness_conformance_label

    if score < 60 or errors >= 3:
        label = "No apta para presentar"
        readiness = "No apta para presentación"
        emoji = readiness_conformance_label(readiness)
    elif errors > 0 or score < 70:
        label = "Requiere correcciones antes de la presentación"
        readiness = "Requiere revisión antes de presentar"
        emoji = readiness_conformance_label(readiness)
    elif warnings > 0 or score < 80:
        label = "Apta con correcciones menores"
        readiness = "Apta con correcciones menores"
        emoji = readiness_conformance_label(readiness)
    else:
        label = "Lista para presentar"
        readiness = "Lista para presentar"
        emoji = readiness_conformance_label(readiness)
    return emoji, label, readiness
