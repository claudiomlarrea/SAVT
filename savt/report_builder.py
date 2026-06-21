from __future__ import annotations

import re

from savt.chapter_reviews import (
    build_chapter_reviews,
    checklist_status_from_reviews,
    readiness_conformance_label,
)
from savt.content_quality import reconcile_section_depth_with_reviews
from savt.models import AuditReport, Finding
from savt.section_audit import (
    build_section_audits,
    detect_document_sections,
    group_findings_by_section,
)
from savt.taxonomy import enrich_finding, icao_interpretation, presentation_status, severity_label

USER_FACING_TITLES: dict[str, str] = {
    "Respuesta a la pregunta de investigación poco explícita": (
        "La respuesta a la pregunta de investigación es poco explícita."
    ),
    "Pregunta no respondida explícitamente en conclusiones": (
        "La pregunta no se responde explícitamente en las conclusiones."
    ),
    "Conclusiones no responden explícitamente la pregunta": (
        "Las conclusiones no responden de forma directa la pregunta de investigación."
    ),
    "Citas APA sin coincidencia exacta en bibliografía": (
        "Se detectaron citas APA sin coincidencia exacta en bibliografía."
    ),
    "DOI inválidos o no resueltos": "Hay DOI inválidos o no resueltos en la bibliografía.",
    "Año bibliográfico distinto al registrado en Crossref": (
        "El año de algunas referencias no coincide con Crossref."
    ),
    "Referencias anteriores al rango metodológico declarado": (
        "Existen referencias anteriores al rango metodológico declarado."
    ),
    "Posible desajuste cita ↔ contenido del párrafo": (
        "Algunas citas parecen poco relacionadas con el párrafo donde aparecen."
    ),
    "Referencias posiblemente ajenas al tema central": (
        "Algunas referencias podrían no estar relacionadas con el tema central."
    ),
    "Referencias bibliográficas no citadas": (
        "Hay referencias bibliográficas que no aparecen citadas en el texto."
    ),
    "Abundancia de párrafos breves": (
        "Hay exceso de párrafos muy breves en la redacción."
    ),
    "Introducción incompleta": "La introducción no incluye todos los elementos esperados.",
    "Metodología con elementos faltantes": "La metodología no desarrolla todos los componentes esperados.",
}

THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bibliografía": ("bibliograf", "cita", "referencia", "doi"),
    "conclusiones": ("conclus", "pregunta"),
    "metodología": ("metodolog", "metodo"),
    "estructura": ("introducc", "estructura", "resultado", "discusi"),
    "figuras": ("figura", "tabla"),
    "redacción": ("estilo", "párrafo", "parrafo", "redacc"),
}

STRENGTH_LABELS: dict[str, str] = {
    "Metodología con componentes principales": "Metodología consistente",
    "Introducción estructuralmente completa": "Introducción bien estructurada",
    "Correspondencia citas APA ↔ bibliografía": "Bibliografía alineada con las citas",
    "Correspondencia citas ↔ bibliografía": "Bibliografía alineada con las citas",
    "Figuras citadas en el texto": "Figuras integradas al texto",
    "Coherencia metodológica documental": "Metodología coherente con el tipo de estudio",
    "Coherencia metodológica empírica": "Metodología empírica coherente",
    "Extensión dentro del rango esperado": "Extensión adecuada",
    "Pregunta respondida en conclusiones": "La pregunta se retoma en las conclusiones",
    "Coherencia objetivos → resultados → conclusiones": "Buena coherencia entre objetivos y cierre",
}

WEAKNESS_LABELS: dict[str, str] = {
    "Respuesta a la pregunta de investigación poco explícita": "Conclusiones poco explícitas",
    "Pregunta no respondida explícitamente en conclusiones": "Conclusiones no responden la pregunta",
    "Conclusiones no responden explícitamente la pregunta": "Conclusiones no responden la pregunta",
    "Citas APA sin coincidencia exacta en bibliografía": "Citas APA sin coincidencia en bibliografía",
    "DOI inválidos o no resueltos": "DOI inválidos o no resueltos",
    "Año bibliográfico distinto al registrado en Crossref": "Años bibliográficos discordantes con Crossref",
    "Posible desajuste cita ↔ contenido del párrafo": "Algunas citas parecen mal ubicadas",
    "Referencias posiblemente ajenas al tema central": "Referencias posiblemente ajenas al tema",
    "Abundancia de párrafos breves": "Exceso de párrafos breves",
    "Introducción incompleta": "Introducción incompleta",
    "Metodología con elementos faltantes": "Metodología con lagunas",
}

BIBLIOGRAPHY_STRENGTH = "Bibliografía alineada con las citas"
BIBLIOGRAPHY_ISSUE_HINTS = (
    "Citas APA sin coincidencia",
    "DOI inválidos",
    "Año bibliográfico distinto",
    "Referencias posiblemente ajenas",
    "Referencias bibliográficas no citadas",
    "Citas sin entrada bibliográfica",
    "Posible desajuste cita",
    "Numeración bibliográfica",
    "Muchas referencias APA no detectadas",
)


def display_title(finding: Finding) -> str:
    return USER_FACING_TITLES.get(finding.title, finding.title if finding.title.endswith(".") else f"{finding.title}.")


def gravity_label(severity: str) -> str:
    return {
        "error": "Grave — corregir antes de entregar",
        "warning": "Moderado — revisar con el director",
        "info": "Menor — mejora recomendada",
    }.get(severity, "")


def build_bibliography_dashboard(report: AuditReport, bib_details: dict) -> dict:
    if bib_details:
        return {
            "style": bib_details.get("style", "—"),
            "style_ok": True,
            "total_refs": bib_details.get("total_refs", 0),
            "citations_found": bib_details.get("citations_found", 0),
            "unmatched_citations": bib_details.get("unmatched_count", 0),
            "out_of_period": len(bib_details.get("out_of_period") or []),
            "possibly_off_topic": bib_details.get("off_topic_count", 0),
            "coverage": bib_details.get("coverage", "—"),
            "details": bib_details,
        }
    return {
        "style": "—",
        "style_ok": False,
        "total_refs": len(report.bibliography),
        "citations_found": 0,
        "unmatched_citations": 0,
        "out_of_period": 0,
        "possibly_off_topic": 0,
        "coverage": "—",
        "details": {},
    }


def _warning_detail_items(finding: Finding, bib_details: dict) -> list[dict]:
    title = finding.title
    items: list[dict] = []

    if "Citas APA sin coincidencia" in title:
        for entry in bib_details.get("unmatched_apa") or []:
            items.append(
                {
                    "label": entry.get("pages_label", "pág. no estimada"),
                    "value": ", ".join(entry.get("citations_in_text") or []),
                    "extra": f"Clave detectada: {entry.get('key', '')}",
                }
            )
    elif "Párrafos duplicados" in title:
        for line in (finding.evidence or "").splitlines():
            line = line.strip()
            if line:
                items.append({"label": "Repetición", "value": line})
    elif "Referencias anteriores al rango" in title:
        for entry in bib_details.get("out_of_period") or []:
            items.append(
                {
                    "label": f"Ref. {entry['number']} ({entry['year']})",
                    "value": entry["summary"],
                    "extra": f"Período declarado: {entry['period_declared']}",
                }
            )
    elif "ajenas al tema" in title:
        for entry in bib_details.get("off_topic") or []:
            items.append(
                {
                    "label": f"Ref. {entry['number']} · {entry.get('pages_label', 'pág. no estimada')}",
                    "value": entry["summary"],
                    "extra": entry.get("reason", ""),
                }
            )
    elif title == "DOI inválidos o no resueltos":
        for entry in bib_details.get("doi_invalid") or []:
            items.append(
                {
                    "label": f"Ref. {entry['number']} — DOI inválido",
                    "value": entry["doi_url"],
                    "extra": entry["message"],
                }
            )
        for entry in bib_details.get("doi_not_resolved") or []:
            items.append(
                {
                    "label": f"Ref. {entry['number']} — DOI no resuelto",
                    "value": entry["doi_url"],
                    "extra": entry["message"],
                }
            )
    elif "Año bibliográfico distinto" in title:
        for entry in bib_details.get("doi_year_mismatch") or []:
            items.append(
                {
                    "label": f"Ref. {entry['number']} · {entry.get('pages_label', 'pág. no estimada')}",
                    "value": (
                        f"Año en bibliografía: {entry['year_in_bibliography']} · "
                        f"Año Crossref: {entry['year_in_crossref']}"
                    ),
                    "extra": f"{entry['doi_url']} — {entry['summary'][:120]}…",
                }
            )
    elif "DOI no verificados por conexión" in title:
        for entry in bib_details.get("doi_network") or []:
            items.append(
                {"label": f"Ref. {entry['number']}", "value": entry["doi_url"], "extra": entry["summary"][:120]}
            )

    if not items and finding.evidence:
        for line in finding.evidence.splitlines()[:15]:
            if line.strip():
                items.append({"label": "Detalle", "value": line.strip()})
    return items


def build_main_reason(findings: list[Finding], chapter_reviews: list[dict]) -> str:
    pending = [r for r in chapter_reviews if not r["ok"]]
    if pending:
        titles = [r["title"] for r in pending[:4]]
        return f"Se requiere revisar: {', '.join(titles)}."

    themes: list[str] = []
    for finding in findings[:6]:
        blob = f"{finding.title} {finding.detail}".lower()
        for theme, hints in THEME_KEYWORDS.items():
            if any(h in blob for h in hints) and theme not in themes:
                themes.append(theme)
    if len(themes) >= 2:
        return f"Se detectaron aspectos a revisar en {' y '.join(themes[:3])}."
    if themes:
        return f"Se detectaron aspectos a revisar en {themes[0]}."
    if findings:
        return display_title(findings[0]).rstrip(".") + "."
    return "No se detectaron problemas prioritarios."


def build_warnings_list(report: AuditReport, bib_details: dict | None = None) -> list[dict]:
    bib_details = bib_details or {}
    items: list[dict] = []
    seen: set[str] = set()
    for finding in report.findings:
        if finding.severity not in ("error", "warning"):
            continue
        title = display_title(finding)
        if title in seen:
            continue
        seen.add(title)
        detail_items = _warning_detail_items(finding, bib_details)
        items.append(
            {
                "title": title,
                "severity": finding.severity,
                "gravity": gravity_label(finding.severity),
                "detail": finding.detail,
                "why": finding.why,
                "how_to_fix": finding.how_to_fix,
                "area": finding.area or finding.module,
                "detail_items": detail_items,
                "finding_title_raw": finding.title,
            }
        )
    order = {"error": 0, "warning": 1}
    items.sort(key=lambda x: order.get(x["severity"], 9))
    return items


def _has_bibliography_issues(report: AuditReport, warnings: list[dict], bib_details: dict) -> bool:
    for finding in report.findings:
        if finding.severity not in ("error", "warning"):
            continue
        if finding.module == "Bibliografía":
            return True
        if any(hint in finding.title for hint in BIBLIOGRAPHY_ISSUE_HINTS):
            return True
    for warning in warnings:
        raw = warning.get("finding_title_raw") or warning.get("title", "")
        if any(hint in raw for hint in BIBLIOGRAPHY_ISSUE_HINTS):
            return True
    if bib_details.get("unmatched_count", 0) > 0:
        return True
    if bib_details.get("coverage") not in ("adecuada", "—", ""):
        return True
    if bib_details.get("doi_invalid") or bib_details.get("doi_not_resolved") or bib_details.get("doi_year_mismatch"):
        return True
    if bib_details.get("off_topic_count", 0) > 0 and any(
        "ajenas al tema" in (w.get("finding_title_raw") or w.get("title", "")) for w in warnings
    ):
        return True
    return False


def _weakness_label(warning: dict) -> str:
    raw = warning["title"].rstrip(".")
    for key, label in WEAKNESS_LABELS.items():
        if key in raw or raw.startswith(key[:20]):
            return label
    return raw


def build_jury_assessment(
    report: AuditReport, warnings: list[dict], bib_details: dict | None = None
) -> dict:
    bib_details = bib_details or {}
    strengths: list[str] = []
    weaknesses: list[str] = []
    bib_issues = _has_bibliography_issues(report, warnings, bib_details)

    for finding in report.findings:
        if finding.severity == "ok" and finding.title in STRENGTH_LABELS:
            label = STRENGTH_LABELS[finding.title]
            if label == BIBLIOGRAPHY_STRENGTH and bib_issues:
                continue
            if label not in strengths:
                strengths.append(label)

    for warning in warnings:
        label = _weakness_label(warning)
        if label not in weaknesses:
            weaknesses.append(label)
        if len(weaknesses) >= 7:
            break

    if bib_issues and BIBLIOGRAPHY_STRENGTH not in weaknesses:
        bib_weaknesses = [w for w in weaknesses if any(h in w.lower() for h in ("cita", "bibliograf", "doi", "referencia"))]
        if not bib_weaknesses:
            weaknesses.insert(0, "Bibliografía con observaciones (citas, DOI o pertinencia)")

    if not strengths:
        strengths = ["Estructura general del trabajo reconocible"]
    if not weaknesses:
        weaknesses = ["Sin debilidades críticas detectadas automáticamente"]

    errors = sum(1 for f in report.findings if f.severity == "error")
    warnings_count = len(warnings)
    score = report.score

    if score >= 85 and errors == 0 and warnings_count <= 1:
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
        "disclaimer": (
            "Estimación heurística basada en hallazgos formales. "
            "No sustituye la evaluación del director ni del jurado examinador."
        ),
    }


def build_submission_checklist(chapter_reviews: list[dict]) -> dict:
    items = []
    for review in chapter_reviews:
        if review["ok"]:
            label = f"{review['title']} completo"
            mark_ok = True
        elif review.get("partial"):
            label = f"{review['title']} — revisión parcial recomendada"
            mark_ok = False
        else:
            label = f"{review['title']} — requiere revisión"
            mark_ok = False

        items.append(
            {
                "label": label,
                "ok": mark_ok,
                "partial": review.get("partial", False),
                "warning": not review["ok"],
                "section_key": review["key"],
            }
        )

    status = checklist_status_from_reviews(chapter_reviews)
    return {"items": items, "status": status}


def prioritize_findings(report: AuditReport) -> list[Finding]:
    order = {"error": 0, "warning": 1, "info": 2}
    hidden_titles = {
        "Estilo de citación detectado: APA",
        "Estilo de citación detectado: NUMBERED",
        "Pregunta de investigación detectada",
        "Pregunta claramente formulada",
        "Objetivos específicos detectados",
    }
    actionable = [
        f
        for f in report.findings
        if f.severity in ("error", "warning", "info")
        and not any(h in f.title for h in hidden_titles)
    ]
    return sorted(actionable, key=lambda f: (order.get(f.severity, 9), f.title))


def build_dashboard(report: AuditReport, parsed: dict, extras: dict) -> dict:
    for finding in report.findings:
        enrich_finding(finding)

    bib_details = extras.get("bibliography_details") or {}
    warnings_list = build_warnings_list(report, bib_details)
    errors = sum(1 for w in warnings_list if w["severity"] == "error")
    warnings = sum(1 for w in warnings_list if w["severity"] == "warning")
    prioritized = prioritize_findings(report)

    bib_dashboard = build_bibliography_dashboard(report, bib_details)
    chapter_reviews = build_chapter_reviews(
        extras.get("structure", {}),
        bib_dashboard,
        warnings_list,
        bool(report.metadata.get("objectives")),
    )
    checklist = build_submission_checklist(chapter_reviews)
    readiness = checklist["status"]
    emoji = readiness_conformance_label(readiness)
    status_label = readiness
    main_reason = build_main_reason(prioritized, chapter_reviews)
    jury = build_jury_assessment(report, warnings_list, bib_details)
    interpretation = icao_interpretation(report.score)

    config = extras.get("config")
    profile_label = report.metadata.get("profile_label", "—")

    content_dashboard = dict(extras.get("content_dashboard") or {})
    if content_dashboard.get("section_depth"):
        content_dashboard["section_depth"] = reconcile_section_depth_with_reviews(
            content_dashboard["section_depth"],
            chapter_reviews,
        )

    detected_sections = extras.get("detected_sections") or detect_document_sections(parsed)
    findings_by_section = group_findings_by_section(report)
    section_audits = build_section_audits(
        detected_sections,
        extras.get("structure", {}),
        content_dashboard.get("section_depth") or [],
        chapter_reviews,
        findings_by_section,
    )

    return {
        "icai": report.score,
        "icai_interpretation": interpretation,
        "presentation_emoji": emoji,
        "presentation_status": status_label,
        "readiness": readiness,
        "main_reason": main_reason,
        "errors": errors,
        "warnings": warnings,
        "warnings_list": warnings_list,
        "prioritized_findings": prioritized,
        "structure": extras.get("structure", {}),
        "objectives_evaluation": extras.get("objectives_evaluation", []),
        "research_question": extras.get("research_question", {}),
        "figures_detail": extras.get("figures_detail", []),
        "tables_detail": extras.get("tables_detail", []),
        "bibliography_dashboard": bib_dashboard,
        "jury": jury,
        "checklist": checklist,
        "chapter_reviews": chapter_reviews,
        "detected_sections": detected_sections,
        "section_audits": section_audits,
        "findings_by_section": findings_by_section,
        "profile_label": profile_label,
        "formal_dashboard": extras.get("formal_dashboard") or {},
        "integrity_dashboard": extras.get("integrity_dashboard") or {},
        "ethics_dashboard": extras.get("ethics_dashboard") or {},
        "content_dashboard": content_dashboard,
        "originality_dashboard": extras.get("originality_dashboard") or {},
    }


def findings_dataframe_rows(report: AuditReport) -> list[dict]:
    rows = []
    for finding in report.findings:
        enrich_finding(finding)
        if finding.severity == "ok":
            continue
        rows.append(
            {
                "Área": finding.area or finding.module,
                "Apartado": finding.section_key or "—",
                "Severidad": severity_label(finding.severity),
                "Gravedad": gravity_label(finding.severity),
                "Hallazgo": display_title(finding),
                "Qué significa": finding.detail,
                "Por qué importa": finding.why,
                "Cómo corregir": finding.how_to_fix,
                "Evidencia": finding.evidence,
            }
        )
    return rows
