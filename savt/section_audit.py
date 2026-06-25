"""Detección de apartados y auditoría consolidada apartado por apartado."""

from __future__ import annotations

from typing import Callable, Optional

from savt.bibliography_styles import extract_apa_citations
from savt.chapter_reviews import CHECK_LABELS, SECTION_TITLES
from savt.content_quality import DEPTH_STATUS_LABELS
from savt.ui_labels import conformance_from_review, depth_status_from_review
from savt.content_quality import _count_citations
from savt.models import AuditReport, Finding
from savt.parser import extract_cited_numbers, _numbered_bibliography_max
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
    """Apartados detectados en el documento (índice preferido; partición sin solapamiento)."""
    if parsed.get("index_sections") and parsed.get("structure_source") == "index":
        sections: list[dict] = []
        for idx, item in enumerate(parsed["index_sections"], start=1):
            sections.append(
                {
                    "role": item.get("role", "otros"),
                    "title": item.get("title", "—"),
                    "detected_as": item.get("title", "—"),
                    "words": item.get("words", 0),
                    "percent": item.get("percent", 0),
                    "percent_label": item.get("percent_label", "—"),
                    "order": idx,
                    "page": item.get("page"),
                    "source": "index",
                }
            )
        return sections

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


def _unique_citations_in_text(text: str, *, style: str, max_ref: int) -> tuple[int, set[int] | set[str]]:
    """Devuelve cantidad y conjunto de referencias/citas distintas en un tramo."""
    if style == "apa" and extract_apa_citations:
        keys, _ = extract_apa_citations(text)
        return len(keys), keys
    refs = extract_cited_numbers(text, max_ref=max_ref)
    return len(refs), refs


def build_citation_reconciliation(
    parsed: dict,
    report: AuditReport,
    bib_dashboard: dict,
) -> dict:
    """
    Cuadre de citas: suma por apartado vs totales del documento y bibliografía.
    «Apariciones» = veces que aparece un paréntesis de cita; «N° refs distintos» = claves/números únicos.
    """
    style = (parsed.get("citation_style") or report.metadata.get("citation_style") or "numbered").lower()
    body = parsed.get("body", "")
    max_ref = _numbered_bibliography_max(report.bibliography) if report.bibliography else 500
    role_texts, _ = get_section_word_partition(parsed)

    section_rows: list[dict] = []
    sum_occurrences = 0
    union_numbered: set[int] = set()
    union_apa: set[str] = set()

    for role, label in CANONICAL_SECTION_ORDER:
        if role == "bibliografia":
            continue
        text = role_texts.get(role, "")
        if not text.strip():
            continue
        occurrences = _count_citations(text)
        unique_count, unique_set = _unique_citations_in_text(text, style=style, max_ref=max_ref)
        sum_occurrences += occurrences
        if style == "apa":
            union_apa |= unique_set  # type: ignore[arg-type]
        else:
            union_numbered |= unique_set  # type: ignore[arg-type]
        section_rows.append(
            {
                "role": role,
                "Apartado": label,
                "Apariciones cita": occurrences,
                "N° refs distintos": unique_count,
            }
        )

    body_occurrences = _count_citations(body)
    if style == "apa":
        union_unique = len(union_apa)
        document_unique = len(report.cited_keys)
        bib_entries = len(report.bibliography)
        uncited = max(0, bib_entries - document_unique)
    else:
        union_unique = len(union_numbered)
        document_unique = len(report.cited_numbers)
        bib_keys = set(report.bibliography.keys())
        uncited = len(bib_keys - report.cited_numbers)

    total_refs = bib_dashboard.get("total_refs", len(report.bibliography))
    unmatched = bib_dashboard.get("unmatched_citations", 0)

    reconciliation_rows = section_rows + [
        {
            "Apartado": "Σ Suma apartados (cuerpo)",
            "Apariciones cita": sum_occurrences,
            "N° refs distintos": union_unique,
            "is_total": True,
        },
        {
            "Apartado": "Documento — cuerpo completo",
            "Apariciones cita": body_occurrences,
            "N° refs distintos": document_unique,
            "is_total": True,
        },
        {
            "Apartado": "Bibliografía — entradas detectadas",
            "Apariciones cita": "—",
            "N° refs distintos": total_refs,
            "is_total": True,
        },
    ]

    notes: list[str] = []
    if union_unique == document_unique:
        notes.append(
            f"Coincide: {union_unique} referencias/citas distintas en la suma por apartados "
            f"= total detectado en el cuerpo."
        )
    else:
        diff = document_unique - union_unique
        notes.append(
            f"Diferencia en refs distintos: Σ apartados {union_unique} vs cuerpo completo "
            f"{document_unique} ({diff:+d}). Puede haber citas en anexos o texto no clasificado."
        )

    if sum_occurrences == body_occurrences:
        notes.append(
            f"Coincide: {sum_occurrences} apariciones de cita en apartados = cuerpo completo."
        )
    else:
        notes.append(
            f"Apariciones de cita: Σ apartados {sum_occurrences} vs cuerpo {body_occurrences} "
            f"({body_occurrences - sum_occurrences:+d} fuera de apartados clasificados)."
        )

    notes.append(
        f"Bibliografía: {total_refs} entradas · Citadas en texto (distintas): {document_unique} · "
        f"No emparejadas: {unmatched} · Entradas no citadas en cuerpo: {uncited}."
    )

    if document_unique > total_refs:
        notes.append(
            f"Alerta: más refs citadas en texto ({document_unique}) que entradas en bibliografía ({total_refs})."
        )

    return {
        "style": style,
        "section_rows": section_rows,
        "reconciliation_rows": reconciliation_rows,
        "notes": notes,
        "sum_occurrences": sum_occurrences,
        "body_occurrences": body_occurrences,
        "union_unique_cited": union_unique,
        "document_unique_cited": document_unique,
        "total_references": total_refs,
        "unmatched_citations": unmatched,
        "uncited_references": uncited,
        "occurrences_aligned": sum_occurrences == body_occurrences,
        "unique_cited_aligned": union_unique == document_unique,
    }


def build_section_audits(
    detected_sections: list[dict],
    structure_dashboard: dict,
    section_depth: list[dict],
    chapter_reviews: list[dict],
    findings_by_section: dict[str, list[dict]] | None = None,
    *,
    bib_dashboard: dict | None = None,
    bibliography_word_count: int = 0,
    parsed: dict | None = None,
    report: AuditReport | None = None,
) -> list[dict]:
    """Consolida métricas, checklist y hallazgos por apartado detectado."""
    depth_by_role = {item.get("role"): item for item in section_depth if item.get("role")}
    review_by_key = {review["key"]: review for review in chapter_reviews}
    findings_by_section = findings_by_section or {}
    style = ""
    max_ref = 500
    role_texts: dict[str, str] = {}
    if parsed and report:
        style = (parsed.get("citation_style") or "numbered").lower()
        max_ref = _numbered_bibliography_max(report.bibliography) if report.bibliography else 500
        role_texts, _ = get_section_word_partition(parsed)

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
        conformance = conformance_from_review(ok, partial)
        if conformance == "—":
            conformance = depth.get("depth_label", "—")

        unique_refs = depth.get("unique_refs_cited", 0)
        if not unique_refs and role_texts.get(role):
            unique_refs, _ = _unique_citations_in_text(
                role_texts[role], style=style or "numbered", max_ref=max_ref
            )

        audits.append(
            {
                "role": role,
                "order": sec.get("order", 0),
                "title": sec["title"],
                "detected_as": sec.get("detected_as") or depth.get("detected_as", "—"),
                "words": sec.get("words", depth.get("words", 0)),
                "percent_label": sec.get("percent_label", "—"),
                "citation_count": depth.get("citation_count", 0),
                "citation_occurrences": depth.get("citation_count", 0),
                "unique_refs_cited": unique_refs,
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
        bib_ok = bib_review.get("ok")
        bib_partial = bib_review.get("partial", False)
        bib_conformance = conformance_from_review(bib_ok, bib_partial)
        bib_depth_status = depth_status_from_review(bib_ok, bib_partial)
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
                "citation_occurrences": "—",
                "unique_refs_cited": citations_found,
                "citation_density": 0,
                "critical_markers": 0,
                "result_markers": 0,
                "depth_status": bib_depth_status,
                "depth_label": DEPTH_STATUS_LABELS.get(bib_depth_status, bib_conformance),
                "depth_reason": bib_review.get("summary", ""),
                "conformance": bib_conformance,
                "review_ok": bib_ok,
                "review_partial": bib_partial,
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
                "Apariciones cita": item.get("citation_occurrences", item.get("citation_count", 0)),
                "N° refs distintos": item.get("unique_refs_cited", "—"),
                "Referencias (bib.)": item.get("reference_count", "—"),
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
