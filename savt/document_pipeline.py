"""Pipeline explícito: índice → apartados → bibliografía → referencias."""

from __future__ import annotations

import re
from typing import Any

from savt.bibliography_styles import (
    detect_citation_style,
    parse_bibliography_by_style,
)
from savt.index_parser import (
    bibliography_index_entry,
    parse_index_entries,
    top_level_index_entries,
)
from savt.index_structure import page_char_offsets, partition_from_index
from savt.models import ReferenceEntry
from savt.word_stats import count_words


def _step(
    step_id: str,
    title: str,
    status: str,
    summary: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "title": title,
        "status": status,
        "summary": summary,
        "details": details,
    }


def _strip_bib_heading(bib_text: str) -> str:
    return re.sub(
        r"^(?:\d+\.?\s*)?(?:[A-ZÁÉÍÓÚÑ]{2,12}\s+)?BIBLIOGRAF[IÍÁ][A-Z]*\s*",
        "BIBLIOGRAFÍA\n",
        bib_text,
        count=1,
        flags=re.IGNORECASE,
    )


def _citations_from_bibliography(
    bibliography: dict[int, ReferenceEntry],
    style: str,
) -> tuple[set[int], set[str]]:
    if style == "apa":
        keys = {ref.key for ref in bibliography.values() if ref.key}
        return set(), keys
    return set(bibliography.keys()), set()


def run_document_pipeline(
    full_text: str,
    *,
    page_texts: list[str] | None = None,
    page_count: int | None = None,
) -> dict[str, Any]:
    """
    Ejecuta el flujo en cuatro momentos:

    1. ÍNDICE → apartados + páginas
    2. Texto del documento → palabras y % por apartado
    3. Último apartado bibliográfico → parse APA o Vancouver
    4. Análisis de referencias solo en bibliografía
    """
    steps: list[dict[str, Any]] = []
    page_offsets = page_char_offsets(page_texts) if page_texts else []

    # —— Paso 1: ÍNDICE ——
    index_entries = parse_index_entries(full_text)
    top_entries = top_level_index_entries(index_entries)
    bib_index = bibliography_index_entry(index_entries)

    if index_entries:
        bib_hint = " con apartado bibliográfico" if bib_index else ""
        step1 = _step(
            "index",
            "1. Índice → apartados y páginas",
            "ok" if top_entries or bib_index else "warning",
            f"Índice detectado{bib_hint}",
            entries=[
                {"number": e.number, "title": e.title, "page": e.page}
                for e in top_entries
            ],
            bibliography_page=bib_index.page if bib_index else None,
            bibliography_title=bib_index.title if bib_index else None,
        )
    else:
        step1 = _step(
            "index",
            "1. Índice → apartados y páginas",
            "warning",
            "No se detectó un índice con páginas. Se usarán encabezados del documento.",
            entries=[],
        )

    steps.append(step1)

    # —— Paso 2: TEXTO → APARTADOS ——
    index_layout = partition_from_index(
        full_text,
        page_offsets=page_offsets,
        page_count=page_count,
    )

    if index_layout and index_layout.get("structure_source") == "index":
        body = index_layout["body"]
        bib_text = index_layout["bibliography_text"]
        section_map = index_layout["section_map"]
        section_meta = index_layout["section_meta"]
        index_sections = index_layout["index_sections"]
        structure_source = "index"
        if not bib_text.strip():
            from savt.parser import split_body_and_bibliography

            split_body, split_bib = split_body_and_bibliography(full_text)
            if split_bib.strip():
                body = split_body
                bib_text = split_bib
        step2_status = "ok"
        step2_summary = "Apartados del índice aplicados al documento"
    else:
        from savt.parser import remove_index_duplicate, split_body_and_bibliography
        from savt.pdf_parser import remove_pdf_front_matter
        from savt.section_resolver import build_enriched_section_map

        body_raw, bib_text = split_body_and_bibliography(full_text)
        body = remove_pdf_front_matter(body_raw) if page_texts else remove_index_duplicate(body_raw)
        section_map, section_meta = build_enriched_section_map(body)
        index_sections = []
        structure_source = "headings"
        body_words_preview = count_words(body)
        step2_status = "warning" if body_words_preview > 8000 and len(section_map) <= 1 else "ok"
        step2_summary = "Apartados detectados por encabezados del documento"

    steps.append(
        _step(
            "sections",
            "2. Texto → palabras y % por apartado",
            step2_status,
            step2_summary,
            source=structure_source,
            sections=index_sections,
        )
    )

    # —— Paso 3: BIBLIOGRAFÍA ——
    bib_for_parse = _strip_bib_heading(bib_text)
    bib_words = count_words(bib_text)

    if not bib_text.strip():
        citation_style = "apa"
        bibliography: dict[int, ReferenceEntry] = {}
        step3 = _step(
            "bibliography",
            "3. Apartado bibliográfico",
            "error",
            "No se localizó el apartado de bibliografía en el documento.",
            style=None,
            references=0,
            words=0,
        )
    else:
        citation_style = detect_citation_style("", bib_for_parse)
        bibliography = parse_bibliography_by_style(bib_for_parse, citation_style)
        step3_status = "ok" if len(bibliography) >= 3 else "warning"
        step3 = _step(
            "bibliography",
            "3. Apartado bibliográfico",
            step3_status,
            f"Apartado bibliográfico detectado",
            style=citation_style,
            references=len(bibliography),
            words=bib_words,
        )

    steps.append(step3)

    # —— Paso 4: ANÁLISIS DE REFERENCIAS (solo bibliografía) ——
    cited_numbers, cited_keys = _citations_from_bibliography(bibliography, citation_style)
    refs_with_key = sum(1 for ref in bibliography.values() if ref.key or ref.raw)
    step4_status = "ok" if len(bibliography) >= 3 else "warning"
    step4_summary = "Análisis del apartado bibliográfico completado (sin escanear el cuerpo)"

    steps.append(
        _step(
            "references",
            "4. Análisis de referencias (solo bibliografía)",
            step4_status,
            step4_summary,
            total=len(bibliography),
            identifiable=refs_with_key,
            cited_keys=len(cited_keys),
            cited_numbers=len(cited_numbers),
            body_scan=False,
        )
    )

    return {
        "steps": steps,
        "body": body,
        "bibliography_text": bib_text,
        "bibliography": bibliography,
        "bibliography_for_parse": bib_for_parse,
        "citation_style": citation_style,
        "cited_numbers": cited_numbers,
        "cited_keys": cited_keys,
        "section_map": section_map,
        "section_meta": section_meta,
        "index_sections": index_sections,
        "index_entries": index_entries,
        "structure_source": structure_source,
        "index_layout": index_layout,
    }
