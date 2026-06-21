"""Detección de apartados y auditoría consolidada apartado por apartado."""

from __future__ import annotations

from typing import Callable, Optional

from savt.chapter_reviews import CHECK_LABELS, SECTION_TITLES
from savt.models import AuditReport, Finding
from savt.word_stats import CANONICAL_SECTION_ORDER, count_words, get_section_word_partition

ProgressCallback = Callable[[str, str, float, Optional[dict]], None]

# Mapeo directo módulo → apartado (prioridad alta).
MODULE_SECTION_MAP: dict[str, str] = {
    "Bibliografía": "bibliografia",
    "Referencias": "bibliografia",
    "Estructura": "",  # resolver por título
    "Contenido": "",  # resolver por título
    "Objetivos": "objetivos",
    "Coherencia": "",  # resolver por título
    "Conclusiones": "conclusiones",
    "Integridad": "transversal",
    "Ética": "transversal",
    "Originalidad": "transversal",
    "Estilo": "transversal",
    "Extensión": "transversal",
    "Formal": "transversal",
    "Similitud": "transversal",
}

# Reglas por título (prioridad sobre coincidencias en el detalle).
TITLE_SECTION_RULES: tuple[tuple[str, str], ...] = (
    ("introducción incompleta", "introduccion"),
    ("marco teórico", "marco_teorico"),
    ("metodología", "metodologia"),
    ("objetivo específico", "objetivos"),
    ("coherencia objetivos", "conclusiones"),
    ("conclus", "conclusiones"),
    ("pregunta no respondida", "conclusiones"),
    ("pregunta de investigación", "introduccion"),
    ("doi inválidos", "bibliografia"),
    ("citas apa", "bibliografia"),
    ("año bibliográfico", "bibliografia"),
    ("referencias bibliográficas", "bibliografia"),
    ("referencias posiblemente", "bibliografia"),
    ("originalidad", "transversal"),
    ("contribución al conocimiento", "conclusiones"),
    ("figura", "resultados"),
    ("tabla", "resultados"),
    ("discusión", "discusion"),
    ("resultado", "resultados"),
)

GLOBAL_SECTIONS = (
    ("integridad", "Integridad académica"),
    ("etica", "Ética de investigación"),
    ("originalidad", "Originalidad y aporte"),
    ("formal", "Normativa formal"),
    ("redaccion", "Redacción y estilo"),
)


def detect_document_sections(parsed: dict) -> list[dict]:
    """Apartados detectados en el documento cargado (partición sin solapamiento)."""
    role_texts, meta = get_section_word_partition(parsed)
    total = max(parsed.get("word_count") or 0, 1)

    sections: list[dict] = []
    for role, label in CANONICAL_SECTION_ORDER:
        text = role_texts.get(role, "")
        words = count_words(text)
        if words <= 0:
            continue
        detected = meta.get(role, {}).get("detected_titles") or []
        pct = round(words * 100 / total, 1)
        sections.append(
            {
                "role": role,
                "title": label,
                "detected_as": detected[0] if detected else label,
                "words": words,
                "percent": pct,
                "percent_label": f"{pct:.1f}%",
                "order": len(sections) + 1,
            }
        )
    return sections


def infer_finding_section(finding: Finding) -> str:
    """Asigna un apartado canónico; prioriza título y módulo sobre el detalle."""
    module_role = MODULE_SECTION_MAP.get(finding.module, "")
    if module_role == "transversal":
        return "transversal"
    if module_role:
        return module_role

    title_lower = (finding.title or "").lower()
    for needle, role in TITLE_SECTION_RULES:
        if needle in title_lower:
            return role

    area_lower = (finding.area or "").lower()
    area_map = {
        "bibliografía": "bibliografia",
        "conclusiones": "conclusiones",
        "metodología": "metodologia",
        "estructura": "",
        "coherencia": "",
        "originalidad": "transversal",
        "integridad": "transversal",
    }
    if area_lower in area_map and area_map[area_lower]:
        return area_map[area_lower]

    return "transversal"


def group_findings_by_section(report: AuditReport) -> dict[str, list[dict]]:
    """Agrupa hallazgos accionables por apartado (excluye transversales)."""
    grouped: dict[str, list[dict]] = {}
    for finding in report.findings:
        if finding.severity == "ok":
            continue
        role = finding.section_key or infer_finding_section(finding)
        if not role or role == "transversal":
            continue
        grouped.setdefault(role, []).append(
            {
                "severity": finding.severity,
                "title": finding.title,
                "detail": finding.detail,
                "why": finding.why,
                "how_to_fix": finding.how_to_fix,
                "area": finding.area or finding.module,
            }
        )
    return grouped


def build_section_audits(
    detected_sections: list[dict],
    structure_dashboard: dict,
    section_depth: list[dict],
    chapter_reviews: list[dict],
    findings_by_section: dict[str, list[dict]] | None = None,
    *,
    bib_dashboard: dict | None = None,
    bibliography_word_count: int = 0,
) -> list[dict]:
    """Consolida métricas, checklist y hallazgos por apartado detectado."""
    depth_by_role = {item.get("role"): item for item in section_depth if item.get("role")}
    review_by_key = {review["key"]: review for review in chapter_reviews}
    findings_by_section = findings_by_section or {}

    audits: list[dict] = []
    for sec in detected_sections:
        role = sec["role"]
        depth = depth_by_role.get(role, {})
        review = review_by_key.get(role, {})
        struct = structure_dashboard.get(role, {})
        checks = struct.get("checks") or review.get("checks") or []
        findings = findings_by_section.get(role, [])

        ok = review.get("ok")
        partial = review.get("partial", False)
        if ok is True:
            conformance = "Conforme"
        elif partial:
            conformance = "Parcialmente conforme"
        elif ok is False:
            conformance = "No conforme"
        else:
            conformance = depth.get("depth_label", "—")

        audits.append(
            {
                "role": role,
                "order": sec.get("order", 0),
                "title": sec["title"],
                "detected_as": sec.get("detected_as") or depth.get("detected_as", "—"),
                "words": sec.get("words", depth.get("words", 0)),
                "percent_label": sec.get("percent_label", "—"),
                "citation_count": depth.get("citation_count", 0),
                "citation_density": depth.get("citation_density", 0),
                "critical_markers": depth.get("critical_markers", 0),
                "result_markers": depth.get("result_markers", 0),
                "depth_status": depth.get("depth_status"),
                "depth_label": depth.get("depth_label", "—"),
                "depth_reason": depth.get("depth_reason", ""),
                "conformance": conformance,
                "review_ok": ok,
                "review_partial": partial,
                "review_summary": review.get("summary", ""),
                "checks": checks,
                "checks_passed": sum(1 for c in checks if c.get("ok")),
                "checks_total": len(checks),
                "missing": review.get("missing") or [],
                "partial_items": review.get("partial_items") or [],
                "why": review.get("why", ""),
                "how_to_fix": review.get("how_to_fix", ""),
                "findings_count": len(findings),
                "findings": findings[:8],
            }
        )

    # Bibliografía: métricas del bloque parseado (no del cuerpo particionado).
    bib_review = review_by_key.get("bibliografia")
    bib = bib_dashboard or {}
    if bib_review and not any(a["role"] == "bibliografia" for a in audits):
        total_refs = bib.get("total_refs", 0)
        citations_found = bib.get("citations_found", 0)
        bib_words = bibliography_word_count or 0
        bib_pct = "—"
        if bib_words and detected_sections:
            body_total = sum(s.get("words", 0) for s in detected_sections)
            if body_total:
                bib_pct = f"{round(bib_words * 100 / (body_total + bib_words), 1):.1f}%"
        audits.append(
            {
                "role": "bibliografia",
                "order": len(audits) + 1,
                "title": SECTION_TITLES.get("bibliografia", "Bibliografía"),
                "detected_as": "Bibliografía / Referencias",
                "words": bib_words,
                "percent_label": bib_pct,
                "reference_count": total_refs,
                "citation_count": citations_found,
                "citation_density": 0,
                "critical_markers": 0,
                "result_markers": 0,
                "depth_status": "adequate" if bib_review.get("ok") else "weak",
                "depth_label": "Conforme" if bib_review.get("ok") else "No conforme",
                "depth_reason": bib_review.get("summary", ""),
                "conformance": "Conforme" if bib_review.get("ok") else "No conforme",
                "review_ok": bib_review.get("ok"),
                "review_partial": bib_review.get("partial", False),
                "review_summary": bib_review.get("summary", ""),
                "checks": bib_review.get("checks") or [],
                "checks_passed": 0,
                "checks_total": 0,
                "missing": bib_review.get("missing") or [],
                "partial_items": bib_review.get("partial_items") or [],
                "why": bib_review.get("why", ""),
                "how_to_fix": bib_review.get("how_to_fix", ""),
                "findings_count": len(findings_by_section.get("bibliografia", [])),
                "findings": findings_by_section.get("bibliografia", [])[:8],
            }
        )

    return audits


def section_audit_summary_rows(section_audits: list[dict]) -> list[dict]:
    """Filas tabulares para UI y exportación."""
    rows = []
    for item in section_audits:
        missing_labels = [
            CHECK_LABELS.get(label, label)
            for label in (item.get("missing") or []) + (item.get("partial_items") or [])
        ]
        rows.append(
            {
                "Orden": item.get("order", ""),
                "Apartado": item.get("title", ""),
                "Detectado como": item.get("detected_as", ""),
                "Palabras": item.get("words", 0),
                "% del cuerpo": item.get("percent_label", "—"),
                "Referencias": item.get("reference_count", "—"),
                "Citas en texto": item.get("citation_count", 0),
                "Densidad citas/100 pal.": item.get("citation_density", 0),
                "Marcadores críticos": item.get("critical_markers", 0),
                "Estado": item.get("conformance", "—"),
                "Profundidad": item.get("depth_label", "—"),
                "Checks OK": (
                    f"{item.get('checks_passed', 0)}/{item.get('checks_total', 0)}"
                    if item.get("checks_total")
                    else "—"
                ),
                "Hallazgos": item.get("findings_count", 0),
                "Observaciones": "; ".join(missing_labels[:3]) if missing_labels else item.get("depth_reason", ""),
            }
        )
    return rows


def tag_findings_with_sections(report: AuditReport) -> None:
    """Completa section_key en hallazgos cuando falta."""
    for finding in report.findings:
        if not finding.section_key:
            finding.section_key = infer_finding_section(finding)
