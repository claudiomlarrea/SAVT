from __future__ import annotations

import re

from savt.audit_config import AuditConfig
from savt.models import Finding

CONTRIBUTION_MARKERS = [
    "este estudio aporta",
    "este trabajo contribuye",
    "la novedad de",
    "el aporte principal",
    "originalidad",
    "primera vez que",
    "nuevo enfoque",
    "nueva perspectiva",
    "hallazgo principal",
    "implicaciones teóricas",
    "implicaciones prácticas",
    "recomendaciones para",
    "líneas futuras",
    "contribución al campo",
    "contribución al conocimiento",
    "en suma",
    "las conclusiones",
    "constituye hoy",
    "factor determinante",
    "desafío que queda",
    "políticas públicas",
    "diagnóstico",
    "traducir este",
]

CONTRIBUTION_PATTERNS = [
    r"\b(aporte|contribuci[oó]n|implicacion|recomendacion|hallazgo|novedad)\w*\b",
    r"\b(en suma|por lo tanto|en conclusi[oó]n)\b",
]

OWN_DATA_MARKERS = [
    "los datos obtenidos",
    "los hallazgos de este estudio",
    "el presente trabajo",
    "nuestros resultados",
    "los resultados obtenidos",
    "elaboración propia",
    "diseño propio",
    "instrumento desarrollado",
    "muestra del estudio",
]

PUBLICATION_MARKERS = [
    "artículo publicado",
    "capítulo de libro",
    "ponencia en",
    "congreso",
    "revista indexada",
]


def audit_originality(parsed: dict, config: AuditConfig) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    body = parsed.get("body", "")
    conclusions = parsed.get("conclusions") or ""
    lower_body = body.lower()
    lower_conc = conclusions.lower()
    level = config.profile.originality_level

    contribution_in_conc = sum(1 for m in CONTRIBUTION_MARKERS if m in lower_conc)
    contribution_in_conc += sum(
        1 for p in CONTRIBUTION_PATTERNS if re.search(p, lower_conc) and len(lower_conc) > 400
    )
    contribution_in_body = sum(1 for m in CONTRIBUTION_MARKERS if m in lower_body)
    own_data = sum(1 for m in OWN_DATA_MARKERS if m in lower_body)
    publications = sum(1 for m in PUBLICATION_MARKERS if m in lower_body)

    dashboard = {
        "contribution_markers": contribution_in_conc + contribution_in_body,
        "own_data_markers": own_data,
        "publication_markers": publications,
        "level": level,
        "score_proxy": 0,
        "indicator_help": {
            "score_proxy": (
                "Puntaje heurístico 0–100 a partir de aporte en conclusiones, datos propios, "
                "publicaciones y completitud general. No mide plagio ni originalidad real."
            ),
            "contribution_markers": (
                "Frases que explicitan aporte, implicaciones, novedad o recomendaciones "
                "en conclusiones y cuerpo del trabajo."
            ),
            "own_data_markers": (
                "Expresiones que señalan hallazgos, datos o instrumentos del estudio "
                "(p. ej. «los resultados obtenidos», «elaboración propia»)."
            ),
            "level": (
                "Exigencia del perfil de titulación: basic (grado/especialización), "
                "standard (maestría) o strict (doctorado). Modifica qué tan estricto es SAVT."
            ),
        },
    }

    if not config.check_originality:
        return findings, dashboard

    proxy = 0
    if contribution_in_conc >= 2:
        proxy += 30
    elif contribution_in_conc >= 1:
        proxy += 15
    if own_data >= 2:
        proxy += 25
    elif own_data >= 1:
        proxy += 10
    if publications >= 1:
        proxy += 15
    objectives = parsed.get("objectives") or []
    obj_eval = parsed.get("_objectives_evaluation")
    if objectives:
        proxy += 10
    if len(parsed.get("bibliography") or {}) >= config.profile.min_references:
        proxy += 10
    dashboard["score_proxy"] = min(proxy, 100)

    if level == "basic":
        if contribution_in_conc < 2 and len(conclusions) > 400:
            findings.append(
                Finding(
                    module="Originalidad",
                    severity="info",
                    title="Aporte personal mejorable en conclusiones",
                    detail=(
                        "Las conclusiones podrían explicitar con mayor claridad "
                        "el aporte al campo o a la práctica profesional."
                    ),
                    how_to_fix=(
                        "Agregue un párrafo final con contribuciones, implicancias y recomendaciones."
                    ),
                )
            )
        elif contribution_in_conc >= 2 or (contribution_in_conc >= 1 and len(conclusions) > 800):
            findings.append(
                Finding(
                    module="Originalidad",
                    severity="ok",
                    title="Aporte personal identificado",
                    detail=f"Marcadores de contribución detectados: {contribution_in_conc + contribution_in_body}.",
                )
            )
        else:
            findings.append(
                Finding(
                    module="Originalidad",
                    severity="ok",
                    title="Conclusiones con cierre argumental detectado",
                    detail="Se identificó desarrollo conclusivo aunque el aporte podría explicitarse más.",
                )
            )
        return findings, dashboard

    if level in ("standard", "strict"):
        if contribution_in_conc < 2:
            findings.append(
                Finding(
                    module="Originalidad",
                    severity="warning" if level == "strict" else "info",
                    title="Contribución al conocimiento poco desarrollada",
                    detail=(
                        f"Marcadores de aporte en conclusiones: {contribution_in_conc}. "
                        f"Nivel esperado para {config.profile.label}: formulación explícita de implicaciones."
                    ),
                    why="CONEAU exige aporte y calidad en trabajos de posgrado.",
                    how_to_fix=(
                        "Desarrolle implicaciones teóricas, prácticas, limitaciones y "
                        "líneas de investigación futura."
                    ),
                )
            )

        if own_data < 1 and level == "strict":
            findings.append(
                Finding(
                    module="Originalidad",
                    severity="warning",
                    title="Escasa evidencia de datos o hallazgos propios",
                    detail=(
                        "No se detectaron marcadores claros de resultados propios del estudio "
                        "(datos, hallazgos, instrumentos)."
                    ),
                    why="Las tesis doctorales deben evidenciar originalidad y aporte al campo.",
                    how_to_fix="Destaque hallazgos originales, datos recogidos y su interpretación.",
                )
            )

        if proxy >= 50:
            findings.append(
                Finding(
                    module="Originalidad",
                    severity="ok",
                    title="Indicadores de originalidad detectables",
                    detail=f"Índice proxy de originalidad: {proxy}/100 (heurístico, no sustituye evaluación experta).",
                )
            )
        elif proxy >= 30:
            findings.append(
                Finding(
                    module="Originalidad",
                    severity="info",
                    title="Originalidad parcialmente explicitada",
                    detail=f"Índice proxy: {proxy}/100. Refuerce formulación de aportes en conclusiones y discusión.",
                )
            )
        else:
            findings.append(
                Finding(
                    module="Originalidad",
                    severity="warning",
                    title="Originalidad difícil de evaluar automáticamente",
                    detail=(
                        f"Índice proxy: {proxy}/100. Pocos indicadores de aporte, datos propios o "
                        "implicaciones en el texto."
                    ),
                    how_to_fix="Consulte con su director sobre el aporte esperado para su nivel de titulación.",
                )
            )

    return findings, dashboard
