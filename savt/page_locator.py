"""Estimación de número de página a partir de la posición en el cuerpo del documento."""

from __future__ import annotations

import re


def total_body_pages(parsed: dict) -> float | None:
    pages = parsed.get("pdf_page_count") or parsed.get("page_estimate_body_only") or parsed.get("page_estimate")
    if pages and float(pages) > 0:
        return float(pages)
    return None


def estimate_page_from_offset(body: str, offset: int, parsed: dict) -> int | None:
    pages = total_body_pages(parsed)
    if not pages or not body or offset < 0:
        return None
    ratio = min(1.0, offset / max(len(body), 1))
    return max(1, min(int(pages), round(ratio * pages) or 1))


def estimate_page_for_snippet(body: str, snippet: str, parsed: dict) -> int | None:
    if not snippet or not body:
        return None
    probe = snippet[:120].strip()
    idx = body.find(probe)
    if idx < 0:
        probe = re.sub(r"\s+", " ", probe)[:80]
        idx = body.find(probe)
    if idx < 0:
        return None
    return estimate_page_from_offset(body, idx, parsed)


def format_pages(pages: list[int] | set[int]) -> str:
    unique = sorted({p for p in pages if p})
    if not unique:
        return "pág. no estimada"
    if len(unique) == 1:
        return f"p. {unique[0]}"
    return "p. " + ", ".join(str(p) for p in unique)


def iter_paragraphs_with_offset(body: str):
    if not body:
        return
    pos = 0
    for block in body.split("\n\n"):
        stripped = block.strip()
        if not stripped:
            pos += len(block) + 2
            continue
        idx = body.find(stripped, pos)
        if idx < 0:
            idx = pos
        yield stripped, idx
        pos = idx + len(stripped) + 2


def pages_for_paragraph(body: str, paragraph: str, parsed: dict) -> int | None:
    return estimate_page_for_snippet(body, paragraph, parsed)


def pages_for_apa_key(body: str, parsed: dict, key: str) -> list[int]:
    pages: set[int] = set()
    for ctx_key, paragraph in parsed.get("citation_contexts_apa", []):
        if ctx_key != key:
            continue
        page = pages_for_paragraph(body, paragraph, parsed)
        if page:
            pages.add(page)
    return sorted(pages)


def pages_for_ref_number(body: str, parsed: dict, ref_num: int) -> list[int]:
    pages: set[int] = set()
    for num, paragraph in parsed.get("citation_contexts", []):
        if num == ref_num:
            page = pages_for_paragraph(body, paragraph, parsed)
            if page:
                pages.add(page)

    for match in re.finditer(rf"\(\s*{ref_num}(?:[,\s\-–]\d+)*\s*\)", body):
        page = estimate_page_from_offset(body, match.start(), parsed)
        if page:
            pages.add(page)

    if parsed.get("citation_style") == "apa":
        bibliography = parsed.get("bibliography") or {}
        ref = bibliography.get(ref_num)
        if ref and ref.key:
            for page in pages_for_apa_key(body, parsed, ref.key):
                pages.add(page)

    return sorted(pages)
