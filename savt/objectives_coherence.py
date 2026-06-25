from __future__ import annotations

import re

from savt.models import Finding
from savt.parser import objectives_headings_present

STOPWORDS = {
    "analizar",
    "analisis",
    "identificar",
    "evaluar",
    "determinar",
    "comparar",
    "estudiar",
    "desarrollar",
    "implementar",
    "mediante",
    "sobre",
    "entre",
    "durante",
    "según",
    "como",
    "para",
    "desde",
    "hacia",
    "modelo",
    "resultados",
    "informe",
}


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-záéíóúñ]{5,}", text.lower())
    return [w for w in words if w not in STOPWORDS][:10]


def _find_results_text(body: str, sections: dict[str, str]) -> str:
    section_map = sections if isinstance(sections, dict) else {}
    for key in ("resultados",):
        if section_map.get(key):
            return section_map[key]
    for key, text in sections.items():
        if any(word in key.lower() for word in ["resultado", "sec_4", "tercera"]):
            return text
    from savt.section_resolver import get_canonical_section

    canonical = get_canonical_section(body, "resultados")
    if canonical:
        return canonical
    match = re.search(r"(?is)resultados.+?(?:discusi|conclusi|\Z)", body)
    return match.group(0) if match else ""


def audit_objectives_coherence(parsed: dict) -> tuple[list[Finding], list[dict]]:
    findings: list[Finding] = []
    objectives = parsed.get("objectives") or []
    body = parsed["body"]
    sections = parsed.get("section_map") or parsed.get("sections", {})
    results_text = _find_results_text(body, sections).lower()
    conclusions = (parsed.get("conclusions") or "").lower()
    evaluations: list[dict] = []

    if not objectives:
        if objectives_headings_present(body):
            findings.append(
                Finding(
                    module="Objetivos",
                    severity="ok",
                    area="Coherencia",
                    title="Objetivo general y objetivos específicos detectados",
                    detail="Se identificaron los apartados por título; la lista específica usa viñetas u otro formato no numerado.",
                    why="Los objetivos guían la evaluación de coherencia interna.",
                )
            )
            return findings, evaluations
        findings.append(
            Finding(
                module="Objetivos",
                severity="warning",
                area="Coherencia",
                title="No se detectaron objetivos específicos",
                detail="No fue posible extraer objetivos del documento.",
                why="Los objetivos guían la evaluación de coherencia interna.",
                how_to_fix="Incluya objetivo general y objetivos específicos en la introducción o marco metodológico.",
            )
        )
        return findings, evaluations

    for idx, objective in enumerate(objectives, start=1):
        keys = _keywords(objective)
        in_results = sum(1 for k in keys if k in results_text)
        in_conclusions = sum(1 for k in keys if k in conclusions)
        total_hits = in_results + in_conclusions

        if in_conclusions >= 2 or (in_results >= 2 and in_conclusions >= 1):
            status = "respondido"
            severity = "ok"
            detail = "El objetivo aparece desarrollado en resultados y/o conclusiones."
        elif total_hits >= 2 or in_results >= 1:
            status = "parcialmente respondido"
            severity = "warning"
            detail = "Hay indicios de desarrollo, pero la respuesta no es plenamente explícita."
        else:
            status = "sin evidencia clara"
            severity = "warning"
            detail = "No se encontraron términos clave del objetivo en resultados ni conclusiones."

        evaluations.append(
            {
                "number": idx,
                "text": objective,
                "status": status,
                "severity": severity,
                "in_results": in_results,
                "in_conclusions": in_conclusions,
            }
        )
        if severity != "ok":
            findings.append(
                Finding(
                    module="Objetivos",
                    severity=severity,
                    area="Coherencia",
                    title=f"Objetivo específico {idx}: {status}",
                    detail=f"{objective[:200]}{'…' if len(objective) > 200 else ''}",
                    evidence=detail,
                    why="Cada objetivo debe tener respuesta verificable en resultados y conclusiones.",
                    how_to_fix="Revise resultados y conclusiones para responder explícitamente este objetivo.",
                )
            )

    responded = sum(1 for e in evaluations if e["status"] == "respondido")
    findings.insert(
        0,
        Finding(
            module="Objetivos",
            severity="ok" if responded == len(objectives) else "info",
            area="Coherencia",
            title="Coherencia objetivos → resultados → conclusiones",
            detail=(
                f"{responded} de {len(objectives)} objetivos con respuesta clara; "
                f"{sum(1 for e in evaluations if e['status'] == 'parcialmente respondido')} parcial(es)."
            ),
        ),
    )
    return findings, evaluations
