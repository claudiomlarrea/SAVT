from __future__ import annotations

import re

from savt.bibliography_styles import apa_keys_match
from savt.models import AuditReport, Finding
from savt.taxonomy import enrich_finding, icao_interpretation, presentation_status, severity_label


def build_bibliography_dashboard(report: AuditReport, parsed: dict) -> dict:
    style = parsed.get("citation_style", "numbered")
    bibliography = report.bibliography
    cited_count = len(report.cited_numbers) or len(report.cited_keys)
    bib_count = len(bibliography)

    unmatched = 0
    if style == "apa":
        bib_keys = {ref.key for ref in bibliography.values() if ref.key}
        unmatched = sum(1 for key in report.cited_keys if not apa_keys_match(key, bib_keys))

    out_of_period = 0
    body = parsed.get("body", "")
    year_range = re.search(r"(20\d{2})\s*[–-]\s*(20\d{2})", body)
    if year_range:
        start_year = int(year_range.group(1))
        out_of_period = sum(
            1
            for ref in bibliography.values()
            if ref.year and ref.year.isdigit() and int(ref.year) < start_year
        )

    off_topic = 0
    keywords = parsed.get("topic_keywords") or []
    if keywords:
        off_topic = sum(
            1
            for ref in bibliography.values()
            if keywords and not any(k in ref.raw.lower() for k in keywords[:6])
        )

    coverage = "adecuada"
    if unmatched > 5 or (bib_count and cited_count / max(bib_count, 1) < 0.6):
        coverage = "requiere revisión"
    elif unmatched > 0 or out_of_period > 5:
        coverage = "aceptable con observaciones"

    return {
        "style": style.upper(),
        "style_ok": True,
        "total_refs": bib_count,
        "citations_found": cited_count,
        "unmatched_citations": unmatched,
        "out_of_period": out_of_period,
        "possibly_off_topic": min(off_topic, bib_count),
        "coverage": coverage,
    }


def build_jury_assessment(report: AuditReport) -> dict:
    strengths: list[str] = []
    weaknesses: list[str] = []

    priority_ok = [
        "Metodología con componentes principales",
        "Introducción estructuralmente completa",
        "Correspondencia citas APA ↔ bibliografía",
        "Correspondencia citas ↔ bibliografía",
        "Figuras citadas en el texto",
        "Coherencia metodológica",
        "Extensión dentro del rango esperado",
    ]
    priority_bad = [
        "Posible desajuste cita ↔ contenido del párrafo",
        "Citas APA sin coincidencia exacta en bibliografía",
        "Respuesta a la pregunta de investigación poco explícita",
        "Pregunta no respondida explícitamente en conclusiones",
        "Conclusiones no responden explícitamente la pregunta",
        "Referencias posiblemente ajenas al tema central",
        "Abundancia de párrafos breves",
    ]

    for finding in report.findings:
        if finding.severity == "ok" and any(p in finding.title for p in priority_ok):
            strengths.append(finding.title)
        if finding.severity in ("error", "warning") and any(p in finding.title for p in priority_bad):
            weaknesses.append(finding.title)

    if not strengths:
        strengths = [f.title for f in report.findings if f.severity == "ok"][:3]
    if not weaknesses:
        weaknesses = [f.title for f in report.findings if f.severity in ("error", "warning")][:3]

    errors = sum(1 for f in report.findings if f.severity == "error")
    warnings = sum(1 for f in report.findings if f.severity == "warning")
    score = report.score

    if score >= 85 and errors == 0 and warnings <= 1:
        probability = "Alta"
    elif score >= 70 and errors == 0:
        probability = "Media-alta"
    elif score >= 60 and errors <= 1:
        probability = "Media"
    else:
        probability = "Baja"

    return {
        "strengths": strengths[:5],
        "weaknesses": weaknesses[:5],
        "approval_probability": probability,
    }


def build_submission_checklist(report: AuditReport, structure: dict, bib_dashboard: dict) -> dict:
    def section_ok(name: str, required_labels: set[str] | None = None) -> bool:
        block = structure.get(name, {})
        checks = block.get("checks", [])
        if not checks:
            return block.get("present", False)
        if required_labels is None:
            required_labels = {c["label"] for c in checks}
        required = [c for c in checks if c["label"] in required_labels]
        return all(c["ok"] for c in required) if required else block.get("present", False)

    intro_ok = section_ok("introduccion", {"pregunta", "objetivos", "problema"})
    objectives_ok = section_ok("introduccion", {"objetivos"}) or bool(report.metadata.get("objectives"))
    method_ok = section_ok("metodologia", {"diseño", "muestra", "variables"})
    results_ok = structure.get("resultados", {}).get("present", False)
    discussion_ok = structure.get("discusion", {}).get("present", False)
    conclusions_ok = structure.get("conclusiones", {}).get("present", False)
    bib_ok = bib_dashboard.get("unmatched_citations", 0) <= 5
    question_ok = not any(
        f.title.startswith("Pregunta no respondida") or f.title.startswith("Conclusiones no responden")
        for f in report.findings
        if f.severity == "warning"
    )

    items = [
        {"label": "Introducción completa", "ok": intro_ok},
        {"label": "Objetivos completos", "ok": objectives_ok},
        {"label": "Metodología completa", "ok": method_ok},
        {"label": "Resultados completos", "ok": results_ok},
        {"label": "Discusión completa", "ok": discussion_ok},
        {"label": "Conclusiones completas", "ok": conclusions_ok},
        {"label": "Bibliografía requiere revisión", "ok": bib_ok, "warning": not bib_ok},
        {"label": "Conclusiones responden la pregunta", "ok": question_ok, "warning": not question_ok},
    ]

    core_items = items[:6]
    secondary_items = items[6:]
    core_ok = sum(1 for i in core_items if i["ok"])
    secondary_warnings = sum(1 for i in secondary_items if not i["ok"])

    if core_ok == len(core_items) and secondary_warnings == 0:
        status = "Lista para presentar"
    elif core_ok >= 5 and secondary_warnings <= 2:
        status = "Apta con correcciones menores"
    elif core_ok >= 4:
        status = "Requiere revisión antes de presentar"
    else:
        status = "No apta para presentar"

    return {"items": items, "status": status}


def prioritize_findings(report: AuditReport) -> list[Finding]:
    order = {"error": 0, "warning": 1, "info": 2, "ok": 3}
    actionable = [f for f in report.findings if f.severity in ("error", "warning", "info")]
    return sorted(actionable, key=lambda f: (order.get(f.severity, 9), f.title))


def build_dashboard(report: AuditReport, parsed: dict, extras: dict) -> dict:
    for finding in report.findings:
        enrich_finding(finding)

    errors = sum(1 for f in report.findings if f.severity == "error")
    warnings = sum(1 for f in report.findings if f.severity == "warning")
    emoji, status_label, readiness = presentation_status(report.score, errors, warnings)
    interpretation = icao_interpretation(report.score)

    prioritized = prioritize_findings(report)
    main_reason = prioritized[0].title if prioritized else "No se detectaron problemas prioritarios."

    bib_dashboard = build_bibliography_dashboard(report, parsed)
    jury = build_jury_assessment(report)
    checklist = build_submission_checklist(report, extras.get("structure", {}), bib_dashboard)

    return {
        "icai": report.score,
        "icai_interpretation": interpretation,
        "presentation_emoji": emoji,
        "presentation_status": status_label,
        "readiness": readiness,
        "main_reason": main_reason,
        "errors": errors,
        "warnings": warnings,
        "prioritized_findings": prioritized,
        "structure": extras.get("structure", {}),
        "objectives_evaluation": extras.get("objectives_evaluation", []),
        "research_question": extras.get("research_question", {}),
        "figures_detail": extras.get("figures_detail", []),
        "tables_detail": extras.get("tables_detail", []),
        "bibliography_dashboard": bib_dashboard,
        "jury": jury,
        "checklist": checklist,
    }


def findings_dataframe_rows(report: AuditReport) -> list[dict]:
    rows = []
    for finding in report.findings:
        enrich_finding(finding)
        rows.append(
            {
                "Área": finding.area or finding.module,
                "Severidad": severity_label(finding.severity),
                "Hallazgo": finding.title,
                "Qué significa": finding.detail,
                "Por qué importa": finding.why,
                "Cómo corregir": finding.how_to_fix,
                "Evidencia": finding.evidence,
            }
        )
    return rows
