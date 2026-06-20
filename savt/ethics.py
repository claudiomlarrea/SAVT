from __future__ import annotations

import re

from savt.audit_config import AuditConfig
from savt.models import Finding

EMPIRICAL_MARKERS = re.compile(
    r"\b(encuesta|entrevista|cuestionario|participantes|pacientes|muestra|"
    r"grupo focal|observación participante|ensayo clínico|campo|etnograf)\b",
    re.IGNORECASE,
)

ETHICS_MARKERS: list[tuple[str, str, str]] = [
    (
        "consentimiento",
        r"consentimiento\s+informado|consentimiento\s+verbal|consentimiento\s+escrito",
        "Consentimiento informado de participantes",
    ),
    (
        "comite_etica",
        r"comit[eé]\s+de\s+[eé]tica|CEI|IRB|institutional review",
        "Aprobación de comité de ética",
    ),
    (
        "confidencialidad",
        r"confidencial|anonimiz|pseudonimiz|protecci[oó]n de datos",
        "Confidencialidad y protección de datos",
    ),
    (
        "declaracion",
        r"declaraci[oó]n\s+(?:de\s+)?(?:[eé]tica|honor|integridad|jurada)",
        "Declaración de ética o integridad",
    ),
    (
        "beneficencia",
        r"beneficencia|no\s+maleficencia|principios?\s+[eé]ticos|declaraci[oó]n de helsinki",
        "Principios éticos declarados",
    ),
    (
        "riesgos",
        r"riesgos?\s+(?:m[ií]nimos|para el participante)|sin\s+riesgos?\s+significativos",
        "Consideración de riesgos para participantes",
    ),
]


def _is_empirical(body: str) -> bool:
    return bool(EMPIRICAL_MARKERS.search(body))


def audit_ethics(parsed: dict, config: AuditConfig) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    body = parsed.get("body", "")
    empirical = _is_empirical(body)
    checklist: list[dict] = []

    for key, pattern, label in ETHICS_MARKERS:
        found = bool(re.search(pattern, body, re.IGNORECASE))
        checklist.append({"key": key, "label": label, "found": found})

    found_count = sum(1 for item in checklist if item["found"])
    dashboard = {
        "is_empirical": empirical,
        "checklist": checklist,
        "found_count": found_count,
        "total": len(checklist),
    }

    if not config.check_ethics:
        return findings, dashboard

    if not empirical and not config.profile.requires_ethics:
        findings.append(
            Finding(
                module="Ética",
                severity="ok",
                title="Estudio documental — revisión ética básica",
                detail="No se detectaron marcadores de investigación con participantes humanos.",
            )
        )
        return findings, dashboard

    if empirical and found_count == 0:
        findings.append(
            Finding(
                module="Ética",
                severity="warning",
                title="Investigación empírica sin mención de aspectos éticos",
                detail=(
                    "Se detectaron encuestas, entrevistas o participantes, pero no referencias "
                    "a consentimiento, comité de ética ni confidencialidad."
                ),
                why="CONEAU y jurados evalúan ética de investigación en trabajos empíricos.",
                how_to_fix=(
                    "Incluya apartado de consideraciones éticas: consentimiento, aprobación "
                    "institucional, confidencialidad y manejo de datos."
                ),
            )
        )
    elif empirical and found_count < 3:
        findings.append(
            Finding(
                module="Ética",
                severity="info",
                title="Aspectos éticos parcialmente documentados",
                detail=f"Se detectaron {found_count}/{len(checklist)} elementos éticos esperados.",
                how_to_fix="Complete consentimiento informado, comité de ética y confidencialidad.",
            )
        )
    elif empirical or config.profile.requires_ethics:
        findings.append(
            Finding(
                module="Ética",
                severity="ok",
                title="Aspectos éticos documentados",
                detail=f"Se detectaron {found_count}/{len(checklist)} elementos éticos en el texto.",
            )
        )

    if config.profile.requires_ethics and not empirical and found_count < 2:
        findings.append(
            Finding(
                module="Ética",
                severity="info",
                title="Posgrado — considere declaración de integridad",
                detail=(
                    f"Perfil {config.profile.label}: se recomienda declaración de ética "
                    "e integridad académica aun en estudios documentales."
                ),
                how_to_fix="Agregue declaración de integridad y uso de fuentes según normativa.",
            )
        )

    return findings, dashboard
