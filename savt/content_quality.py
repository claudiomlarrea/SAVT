from __future__ import annotations

import re

from savt.audit_config import AuditConfig
from savt.document_sections import extract_section, get_section_map
from savt.models import Finding
from savt.word_stats import build_word_statistics, count_words

CRITICAL_MARKERS = [
    "sin embargo",
    "no obstante",
    "por el contrario",
    "cabe señalar",
    "limitaciones de",
    "autores como",
    "según",
    "frente a",
    "en contraste",
    "critican",
    "cuestionan",
    "debate",
    "controversia",
]

HYPOTHESIS_PATTERNS = [
    r"hip[oó]tesis\s+(?:de\s+investigaci[oó]n|general|n[°º]?\s*\d)",
    r"hip[oó]tesis\s*:",
    r"se\s+plantea\s+la\s+hip[oó]tesis",
]

RESULTS_MARKERS = [
    "los resultados muestran",
    "se encontró",
    "se observó",
    "el análisis reveló",
    "los datos indican",
    "hallazgo",
    "figura",
    "tabla",
    "gráfico",
]


def _marco_text(parsed: dict) -> str:
    section_map = parsed.get("section_map") or get_section_map(parsed.get("body", ""))
    marco = section_map.get("marco_teorico", "")
    if len(marco) > 400:
        return marco
    return extract_section(
        parsed.get("body", ""),
        (
            "marco teórico",
            "marco teorico",
            "marco conceptual",
            "revisión de literatura",
            "revision de literatura",
            "antecedentes",
            "estado del arte",
        ),
    )


def audit_content_quality(parsed: dict, config: AuditConfig) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    body = parsed.get("body", "")
    marco = _marco_text(parsed)
    word_stats = build_word_statistics(parsed)
    dashboard: dict = {
        **word_stats,
        "marco_word_count": count_words(marco) if marco else 0,
        "citation_density_marco": 0.0,
        "critical_markers_found": 0,
        "hypothesis_detected": False,
        "results_development": "unknown",
        "indicator_help": {
            "total_body_words": (
                "Palabras del cuerpo del trabajo (sin bibliografía ni anexos finales parseados)."
            ),
            "bibliography_words": "Palabras detectadas en la sección de bibliografía/referencias.",
            "sections": (
                "Extensión bajo cada encabezado detectado y su porcentaje sobre el total del cuerpo. "
                "Subsecciones pueden solaparse con capítulos padre; la suma puede superar 100%."
            ),
            "marco_word_count": (
                "Palabras en marco teórico / revisión bibliográfica (rol canónico). "
                "Puede solaparse con filas del desglose por apartados."
            ),
            "citation_density_marco": (
                "Promedio de citas bibliográficas cada 100 palabras del marco teórico. "
                "Valores más altos suelen reflejar mayor apoyo documental."
            ),
            "critical_markers_found": (
                "Expresiones de análisis crítico (contrastes, autores citados, limitaciones, debates). "
                "Cuenta indicios de lectura activa, no profundidad por sí sola."
            ),
        },
    }

    if not config.check_content_depth:
        return findings, dashboard

    if marco:
        critical_found = sum(1 for m in CRITICAL_MARKERS if m in marco.lower())
        dashboard["critical_markers_found"] = critical_found
        marco_words = dashboard["marco_word_count"]
        words = max(marco_words, 1)
        cites = len(re.findall(r"\(\d+(?:[,\s\-–]\d+)*\)", marco))
        cites += len(re.findall(r"\([A-ZÁÉÍÓÚÑ][^)]*,\s*\d{4}", marco))
        density = round(cites / (words / 100), 2)
        dashboard["citation_density_marco"] = density

        if marco_words < 800:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Marco teórico breve para el nivel del trabajo",
                    detail=f"Marco teórico detectado: ~{marco_words} palabras.",
                    why="Los jurados suelen valorar profundidad en revisión de literatura.",
                    how_to_fix="Amplíe síntesis crítica de autores clave, debates y vacíos de conocimiento.",
                )
            )
        elif critical_found >= 3 or density >= 1.5:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="ok",
                    title="Marco teórico con desarrollo detectable",
                    detail=(
                        f"Extensión ~{marco_words} palabras, densidad de citas {density}/100, "
                        f"marcadores críticos: {critical_found}."
                    ),
                )
            )
        else:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Marco teórico descriptivo",
                    detail="El marco podría reforzar contraste, debate o crítica explícita.",
                    how_to_fix="Contraste autores y relacione teorías con su problema de investigación.",
                )
            )
    else:
        findings.append(
            Finding(
                module="Contenido",
                severity="warning",
                title="Marco teórico no identificado claramente",
                detail="No se detectó sección de marco teórico, revisión de literatura o antecedentes.",
                why="El marco teórico es dimensión central en evaluaciones académicas.",
                how_to_fix="Incluya capítulo o sección dedicada al marco vinculada al problema.",
            )
        )

    hypothesis_found = any(re.search(p, body, re.IGNORECASE) for p in HYPOTHESIS_PATTERNS)
    dashboard["hypothesis_detected"] = hypothesis_found

    section_map = parsed.get("section_map") or get_section_map(body)
    results_section = section_map.get("resultados", "")
    if not results_section:
        match = re.search(r"(?is)(resultados.+?)(?:discusi[oó]n|conclusiones|bibliograf)", body)
        results_section = match.group(1) if match else ""

    if results_section:
        result_markers = sum(1 for m in RESULTS_MARKERS if m in results_section.lower())
        dashboard["results_development"] = "adequate" if result_markers >= 2 else "weak"

    return findings, dashboard
