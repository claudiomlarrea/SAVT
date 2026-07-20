"""Detección de apartados y auditoría consolidada apartado por apartado."""

from __future__ import annotations

from typing import Callable, Optional

from savt.bibliography_styles import extract_apa_citations
from savt.chapter_reviews import CHECK_LABELS, SECTION_TITLES
from savt.content_quality import DEPTH_STATUS_LABELS
from savt.ui_labels import conformance_from_review, depth_status_from_review
from savt.models import AuditReport, Finding
from savt.parser import extract_cited_numbers, _numbered_bibliography_max
from savt.citations import count_citation_appearances, strip_embedded_bibliographies
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
    ("discusiones", "discusion"),
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
    """Apartados detectados: preferir contrato document_model; si no, índice/mapa."""
    from savt.document_model import (
        ensure_document_model,
        flatten_document_model_for_display,
    )
    from savt.structure_confirm import enrich_detected_sections

    structure_source = str(parsed.get("structure_source") or "")
    model = ensure_document_model(parsed)
    if model.get("chapters") and structure_source in {
        "index",
        "confirmed",
        "capitulos",
        "manual",
    }:
        sections = flatten_document_model_for_display(model)
        # Alinear source con la fuente real de detección
        for item in sections:
            item["source"] = (
                "manual"
                if structure_source == "manual"
                else "index"
                if structure_source == "index"
                else "capitulos"
                if structure_source == "capitulos"
                else "confirmed"
            )
        return enrich_detected_sections(sections, structure_source=structure_source)

    if parsed.get("index_sections") and structure_source in {"index", "confirmed", "capitulos", "manual"}:
        sections = []
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
                    "level": item.get("level", 1),
                    "path": item.get("path") or item.get("title"),
                    "source": (
                        "manual"
                        if structure_source == "manual"
                        else "index"
                        if structure_source == "index"
                        else "capitulos"
                        if structure_source == "capitulos"
                        else "confirmed"
                    ),
                }
            )
        return enrich_detected_sections(sections, structure_source=structure_source)

    role_texts, meta = get_section_word_partition(parsed)
    total = max(parsed.get("word_count") or 0, 1)

    sections = []
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
                "user_confirmed": bool(meta.get(role, {}).get("user_confirmed")),
            }
        )
    return enrich_detected_sections(sections, structure_source=structure_source)


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


def _text_span(full_text: str, start, end) -> str:
    if start is None or end is None or not full_text:
        return ""
    try:
        return full_text[int(start) : int(end)]
    except (TypeError, ValueError):
        return ""


def _chapter_citation_rows(
    parsed: dict,
    *,
    style: str,
    max_ref: int,
) -> list[dict]:
    """Filas de citas por capítulos reales del árbol (preferido en compendios)."""
    tree = parsed.get("structure_tree") or []
    full_text = parsed.get("full_text") or parsed.get("body") or ""
    if not tree or not full_text:
        return []

    rows: list[dict] = []
    for node in tree:
        text = strip_embedded_bibliographies(
            _text_span(full_text, node.get("start"), node.get("end"))
        )
        if count_words(text) < 40:
            continue
        occurrences = count_citation_appearances(text, style=style, max_ref=max_ref)
        unique_count, _ = _unique_citations_in_text(text, style=style, max_ref=max_ref)
        role = str(node.get("role") or "otros")
        role_label = SECTION_TITLES.get(role, role.replace("_", " ").title())
        title = str(node.get("title") or "Capítulo")
        rows.append(
            {
                "Apartado": title,
                "Rol académico": role_label if role not in {"otros", "omitir"} else "—",
                "Apariciones cita": occurrences,
                "N° refs distintos": unique_count,
                "Tipo": "Capítulo",
                "words": count_words(text),
            }
        )
        for child in node.get("children") or []:
            child_role = str(child.get("role") or "otros")
            if child_role in {"otros", "omitir"}:
                continue
            child_text = strip_embedded_bibliographies(
                _text_span(full_text, child.get("start"), child.get("end"))
            )
            if count_words(child_text) < 40:
                continue
            child_occ = count_citation_appearances(child_text, style=style, max_ref=max_ref)
            child_unique, _ = _unique_citations_in_text(child_text, style=style, max_ref=max_ref)
            rows.append(
                {
                    "Apartado": f"  {child.get('title')}",
                    "Rol académico": SECTION_TITLES.get(child_role, child_role),
                    "Apariciones cita": child_occ,
                    "N° refs distintos": child_unique,
                    "Tipo": "Sección",
                    "words": count_words(child_text),
                }
            )
    return rows


def build_citation_reconciliation(
    parsed: dict,
    report: AuditReport,
    bib_dashboard: dict,
) -> dict:
    """
    Cuadre de citas con dos métricas distintas:

    - Apariciones: veces que se colocó una cita en el texto (la misma ref puede repetirse).
    - Refs distintas: claves/números únicos (totales del documento o por apartado).
    """
    style = (parsed.get("citation_style") or report.metadata.get("citation_style") or "numbered").lower()
    body = strip_embedded_bibliographies(parsed.get("body", ""))
    max_ref = _numbered_bibliography_max(report.bibliography) if report.bibliography else 500

    chapter_rows = _chapter_citation_rows(parsed, style=style, max_ref=max_ref)
    section_rows: list[dict] = []
    sum_occurrences = 0
    union_numbered: set[int] = set()
    union_apa: set[str] = set()

    if chapter_rows:
        full_text = parsed.get("full_text") or parsed.get("body") or ""
        tree = parsed.get("structure_tree") or []
        for row in chapter_rows:
            if row.get("Tipo") != "Capítulo":
                continue
            sum_occurrences += int(row.get("Apariciones cita") or 0)
            title = row["Apartado"]
            for node in tree:
                if str(node.get("title")) == title:
                    text = strip_embedded_bibliographies(
                        _text_span(full_text, node.get("start"), node.get("end"))
                    )
                    _, unique_set = _unique_citations_in_text(text, style=style, max_ref=max_ref)
                    if style == "apa":
                        union_apa |= unique_set  # type: ignore[arg-type]
                    else:
                        union_numbered |= unique_set  # type: ignore[arg-type]
                    break
        section_rows = [
            {k: v for k, v in row.items() if k != "words"} for row in chapter_rows
        ]
    else:
        role_texts, _ = get_section_word_partition(parsed)
        for role, label in CANONICAL_SECTION_ORDER:
            if role == "bibliografia":
                continue
            text = strip_embedded_bibliographies(role_texts.get(role, ""))
            if not text.strip():
                continue
            occurrences = count_citation_appearances(text, style=style, max_ref=max_ref)
            unique_count, unique_set = _unique_citations_in_text(text, style=style, max_ref=max_ref)
            sum_occurrences += occurrences
            if style == "apa":
                union_apa |= unique_set  # type: ignore[arg-type]
            else:
                union_numbered |= unique_set  # type: ignore[arg-type]
            section_rows.append(
                {
                    "Apartado": label,
                    "Rol académico": label,
                    "Apariciones cita": occurrences,
                    "N° refs distintos": unique_count,
                    "Tipo": "Apartado",
                }
            )

    body_occurrences = count_citation_appearances(body, style=style, max_ref=max_ref)
    if chapter_rows and sum_occurrences:
        # En compendio el cuerpo puede haberse truncado; el total fiable es la suma de capítulos.
        body_occurrences = sum_occurrences

    if style == "apa":
        from savt.bibliography_styles import apa_keys_match

        text_keys = union_apa if union_apa else set(report.cited_keys or [])
        if not text_keys and report.cited_keys:
            text_keys = set(report.cited_keys)
        bib_keys = {ref.key for ref in report.bibliography.values() if ref.key}
        matched_bib = {bk for bk in bib_keys if apa_keys_match(bk, text_keys)}
        # Totales de usuario: cuántas de las entradas de la bib aparecen en el texto
        document_unique = len(matched_bib)
        union_unique = len(matched_bib)
        uncited = len(bib_keys - matched_bib)
        text_unique_raw = len(text_keys)
    else:
        cited_nums = set(report.cited_numbers or [])
        if not cited_nums and union_numbered:
            cited_nums = set(union_numbered)
        bib_keys_n = set(report.bibliography.keys())
        matched = cited_nums & bib_keys_n if bib_keys_n else cited_nums
        document_unique = len(matched)
        union_unique = len(matched)
        uncited = len(bib_keys_n - cited_nums) if bib_keys_n else 0
        text_unique_raw = len(cited_nums)

    total_refs = bib_dashboard.get("total_refs", len(report.bibliography))
    unmatched = bib_dashboard.get("unmatched_citations", 0)

    reconciliation_rows = section_rows + [
        {
            "Apartado": "TOTAL documento (cuerpo)",
            "Rol académico": "—",
            "Apariciones cita": body_occurrences,
            "N° refs distintos": text_unique_raw,
            "Refs bib. emparejadas": document_unique,
            "Tipo": "Total / resumen",
        },
    ]

    notes: list[str] = [
        f"Estilo: {'APA (autor-año)' if style == 'apa' else 'Numerado'}.",
        (
            f"**Apariciones ({body_occurrences})** = veces que se colocó una cita en el texto. "
            f"Sí: es cuántas veces se usan las referencias a lo largo del documento "
            f"(una misma de las {total_refs} puede citarse muchas veces)."
        ),
        (
            f"**Fuentes únicas en el texto ({text_unique_raw})** = autor-año distintos detectados en el cuerpo."
        ),
        (
            f"**Entradas bibliográficas emparejadas ({document_unique})** = "
            f"cuántas de las {total_refs} entradas de la lista aparecen citadas al menos una vez."
        ),
        (
            f"**Bibliografía:** {total_refs} entradas · Citadas ≥1 vez: {document_unique} · "
            f"No citadas: {uncited} · Citas del texto sin emparejar: {unmatched}."
        ),
    ]
    if style == "apa" and text_unique_raw and text_unique_raw != document_unique:
        notes.append(
            f"En el texto se detectaron {text_unique_raw} formas autor-año distintas; "
            f"{document_unique} coinciden con entradas de la bibliografía."
        )
    if chapter_rows:
        notes.append(
            "En cada capítulo, «refs distintas» son locales: la misma fuente en Cap. 1 y Cap. 2 "
            "cuenta en ambos, pero en el TOTAL del documento solo una vez."
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
        "text_unique_raw": text_unique_raw,
        "total_references": total_refs,
        "unmatched_citations": unmatched,
        "uncited_references": uncited,
        "occurrences_aligned": True,
        "unique_cited_aligned": True,
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
    full_text = (parsed or {}).get("full_text") or (parsed or {}).get("body") or ""
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

        span_text = strip_embedded_bibliographies(
            _text_span(full_text, sec.get("start"), sec.get("end"))
        )
        text_for_cites = span_text or strip_embedded_bibliographies(role_texts.get(role, ""))
        unique_refs = 0
        occurrences: int | str = 0
        if text_for_cites.strip():
            unique_refs, _ = _unique_citations_in_text(
                text_for_cites, style=style or "numbered", max_ref=max_ref
            )
            occurrences = count_citation_appearances(
                text_for_cites, style=style or "numbered", max_ref=max_ref
            )
        elif depth.get("unique_refs_cited"):
            unique_refs = depth.get("unique_refs_cited", 0)
            occurrences = depth.get("citation_count", 0)

        audits.append(
            {
                "role": role,
                "order": sec.get("order", 0),
                "title": sec["title"],
                "detected_as": sec.get("detected_as") or depth.get("detected_as", "—"),
                "words": sec.get("words", depth.get("words", 0)),
                "percent_label": sec.get("percent_label", "—"),
                "citation_count": occurrences if occurrences != "—" else 0,
                "citation_occurrences": occurrences,
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
    """Filas tabulares para UI y exportación (alineadas a la hoja Auditoría por apartado)."""
    rows = []
    for item in section_audits:
        missing_labels = [
            CHECK_LABELS.get(label, label)
            for label in (item.get("missing") or []) + (item.get("partial_items") or [])
        ]
        obs = "; ".join(missing_labels[:3]) if missing_labels else (item.get("review_summary") or item.get("depth_reason") or "")
        rows.append(
            {
                "Orden": item.get("order", ""),
                "Apartado": item.get("title", ""),
                "Palabras": item.get("words", 0),
                "% del cuerpo": item.get("percent_label", "—"),
                "Refs distintas citadas": item.get("unique_refs_cited", "—"),
                "Apariciones de cita": item.get("citation_occurrences", item.get("citation_count", 0)),
                "Referencias (bib.)": item.get("reference_count", "—"),
                "Estado": item.get("conformance", "—"),
                "Hallazgos": item.get("findings_count", 0),
                "Observaciones": (obs[:220] + "…") if len(str(obs)) > 220 else obs,
            }
        )
    return rows


def section_audit_ui_rows(section_audits: list[dict]) -> list[dict]:
    """Vista ejecutiva: estado + apariciones + refs distintas (sin confundir con entradas bib)."""
    rows = []
    for item in section_audits:
        if item.get("role") == "bibliografia":
            rows.append(
                {
                    "Apartado": item.get("title", "Bibliografía"),
                    "Palabras": item.get("words", 0),
                    "Veces citadas": "—",
                    "Refs distintas": "—",
                    "Entradas bib.": item.get("reference_count", "—"),
                    "Estado": item.get("conformance", "—"),
                }
            )
            continue
        missing_labels = [
            CHECK_LABELS.get(label, label)
            for label in (item.get("missing") or []) + (item.get("partial_items") or [])
        ]
        obs = "; ".join(missing_labels[:3]) if missing_labels else (item.get("review_summary") or "")
        rows.append(
            {
                "Apartado": item.get("title", ""),
                "Palabras": item.get("words", 0),
                "Veces citadas": item.get("citation_occurrences", item.get("citation_count", 0)),
                "Refs distintas": item.get("unique_refs_cited", "—"),
                "Estado": item.get("conformance", "—"),
                "Observaciones": (str(obs)[:160] + "…") if len(str(obs)) > 160 else (obs or "—"),
            }
        )
    return rows


def tag_findings_with_sections(report: AuditReport) -> None:
    """Completa section_key en hallazgos cuando falta."""
    for finding in report.findings:
        if not finding.section_key:
            finding.section_key = infer_finding_section(finding)
