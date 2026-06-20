from __future__ import annotations

import re
from collections import Counter

from savt.audit_config import AuditConfig
from savt.models import Finding

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

MARCO_PATTERNS = [
    r"marco\s+te[oó]rico",
    r"marco\s+conceptual",
    r"fundamentaci[oó]n\s+te[oó]rica",
    r"revisi[oó]n\s+(?:de\s+)?(?:la\s+)?literatura",
    r"estado\s+(?:del\s+)?arte",
    r"antecedentes",
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
]


def _marco_text(body: str, sections: dict | None = None) -> str:
    if sections:
        for key, text in sections.items():
            key_l = key.lower()
            if any(
                token in key_l
                for token in ("marco", "teor", "literatura", "antecedente", "fundament")
            ):
                if len(text) > 400:
                    return text

    for pattern in MARCO_PATTERNS:
        match = re.search(
            rf"({pattern}.{{0,40}})(.+?)(?:\n(?:CAPÍTULO|CAPITULO|\d+\.\s+Metodolog|\d+\.\s+METODOLOG))",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        if match and len(match.group(0)) > 500:
            return match.group(0)
    for key, text in _split_by_chapter(body).items():
        if any(p in key.lower() for p in ("marco", "teor", "literatura", "antecedente")):
            return text
    return ""


def _split_by_chapter(body: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    chunks = re.split(r"(?m)^(CAPÍTULO|CAPITULO)\s+", body)
    if len(chunks) < 2:
        return {"general": body}
    for chunk in chunks[1:]:
        lines = chunk.split("\n", 1)
        title = lines[0][:60].strip()
        content = lines[1] if len(lines) > 1 else ""
        parts[title.lower()] = content
    return parts


def _citation_density(text: str) -> float:
    if not text:
        return 0.0
    words = max(len(re.findall(r"\b\w+\b", text)), 1)
    cites = len(re.findall(r"\(\d+(?:[,\s\-–]\d+)*\)", text))
    cites += len(re.findall(r"\([A-ZÁÉÍÓÚÑ][^)]*,\s*\d{4}", text))
    return round(cites / (words / 100), 2)


def audit_content_quality(parsed: dict, config: AuditConfig) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    body = parsed.get("body", "")
    marco = _marco_text(body, parsed.get("sections"))
    dashboard: dict = {
        "marco_word_count": len(re.findall(r"\b\w+\b", marco)) if marco else 0,
        "citation_density_marco": _citation_density(marco),
        "critical_markers_found": 0,
        "hypothesis_detected": False,
        "results_development": "unknown",
    }

    if not config.check_content_depth:
        return findings, dashboard

    if marco:
        critical_found = sum(1 for m in CRITICAL_MARKERS if m in marco.lower())
        dashboard["critical_markers_found"] = critical_found
        marco_words = dashboard["marco_word_count"]
        density = dashboard["citation_density_marco"]

        if marco_words < 800:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="warning",
                    title="Marco teórico breve para el nivel del trabajo",
                    detail=f"Marco teórico detectado: ~{marco_words} palabras.",
                    why="Las rúbricas UNCUyo y CONEAU exigen profundidad en revisión de literatura.",
                    how_to_fix="Amplíe síntesis crítica de autores clave, debates y vacíos de conocimiento.",
                )
            )
        elif density < 1.5 and marco_words > 500:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Marco teórico con baja densidad de citas",
                    detail=(
                        f"Densidad de citas en marco: {density} por 100 palabras. "
                        "Puede indicar descripción sin sustento bibliográfico."
                    ),
                    how_to_fix="Integre más referencias al desarrollar cada concepto o autor.",
                )
            )
        elif critical_found >= 3:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="ok",
                    title="Marco teórico con análisis crítico detectable",
                    detail=(
                        f"Marcadores de análisis crítico: {critical_found}. "
                        f"Extensión ~{marco_words} palabras, densidad de citas {density}/100."
                    ),
                )
            )
        else:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Marco teórico descriptivo",
                    detail=(
                        "El marco parece más descriptivo que analítico. "
                        "Pocos marcadores de contraste, debate o crítica."
                    ),
                    how_to_fix=(
                        "Contraste autores, señale vacíos, relacione teorías con su problema "
                        "de investigación."
                    ),
                )
            )

        years = [int(y) for y in re.findall(r"\b(20\d{2}|19\d{2})\b", marco)]
        if years:
            recent = sum(1 for y in years if y >= 2018)
            dashboard["recent_refs_ratio"] = round(recent / len(years), 2)
            if recent / len(years) < 0.3 and len(years) >= 5:
                findings.append(
                    Finding(
                        module="Contenido",
                        severity="info",
                        title="Marco teórico con bibliografía poco actualizada",
                        detail=(
                            f"Solo {recent}/{len(years)} referencias en marco son de 2018 en adelante."
                        ),
                        how_to_fix="Incorpore literatura reciente (últimos 5–7 años) en el marco teórico.",
                    )
                )
    else:
        findings.append(
            Finding(
                module="Contenido",
                severity="warning",
                title="Marco teórico no identificado claramente",
                detail="No se detectó sección de marco teórico, revisión de literatura o antecedentes.",
                why="El marco teórico es dimensión central en todas las rúbricas evaluadas.",
                how_to_fix="Incluya capítulo o sección dedicada al marco teórico vinculada al problema.",
            )
        )

    hypothesis_found = any(re.search(p, body, re.IGNORECASE) for p in HYPOTHESIS_PATTERNS)
    dashboard["hypothesis_detected"] = hypothesis_found
    empirical = bool(
        re.search(r"\b(encuesta|experimento|muestra|hipótesis|variable)\b", body, re.IGNORECASE)
    )
    if empirical and not hypothesis_found:
        findings.append(
            Finding(
                module="Contenido",
                severity="info",
                title="Estudio empírico sin hipótesis explícita",
                detail="No se detectó formulación de hipótesis de investigación.",
                how_to_fix=(
                    "Si aplica a su diseño, formule hipótesis testeables vinculadas a objetivos "
                    "y variables."
                ),
            )
        )

    results_section = ""
    for key, text in _split_by_chapter(body).items():
        if "resultado" in key:
            results_section = text
            break
    if not results_section:
        match = re.search(
            r"(?is)(resultados.+?)(?:discusi[oó]n|conclusiones|bibliograf)",
            body,
        )
        results_section = match.group(1) if match else ""

    if results_section:
        result_markers = sum(1 for m in RESULTS_MARKERS if m in results_section.lower())
        dashboard["results_development"] = "adequate" if result_markers >= 2 else "weak"
        if result_markers < 2 and len(results_section) > 400:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Sección de resultados poco desarrollada",
                    detail="Los resultados podrían presentarse con mayor detalle analítico.",
                    how_to_fix="Organice hallazgos, referencie figuras/tablas e interprete datos.",
                )
            )

    return findings, dashboard
