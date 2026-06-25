"""Extracción de apartados desde el ÍNDICE del documento."""

from __future__ import annotations

import re
from dataclasses import dataclass

from savt.section_resolver import classify_heading

INDEX_HEADING = re.compile(r"(?im)^\s*ÍNDICE\s*$|^\s*INDICE\s*$|^\s*TABLA DE CONTENIDO\s*$")
INDEX_LINE = re.compile(
    r"(?m)^\s*(\d{1,2})(?:\.(?![0-9])|\s+)\s*(.+?)\s*\(pag\.\s*(\d+)\s*\)",
    re.IGNORECASE,
)
BIBLIOGRAPHY_TITLE = re.compile(r"(?i)bibliograf|referencias\s+bibliogr|referencias\s*$")


@dataclass(frozen=True)
class IndexEntry:
    number: str
    title: str
    page: int
    role: str | None = None

    @property
    def is_bibliography(self) -> bool:
        return bool(BIBLIOGRAPHY_TITLE.search(self.title))


def _index_block(full_text: str) -> str:
    """Recorta el bloque de índice (portada → primer apartado con pag.)."""
    match = INDEX_HEADING.search(full_text)
    if match:
        start = match.end()
        chunk = full_text[start : start + 12000]
    else:
        # Sin encabezado «ÍNDICE»: buscar agrupación de líneas (pag. N) al inicio.
        head = full_text[: min(len(full_text), 25000)]
        first_pag = re.search(r"\(pag\.\s*\d+\s*\)", head, re.I)
        if not first_pag or first_pag.start() > 8000:
            return ""
        chunk = head[max(0, first_pag.start() - 4000) : first_pag.start() + 8000]

    # Cortar cuando deja de haber entradas con (pag. N).
    lines = chunk.splitlines()
    kept: list[str] = []
    empty_run = 0
    for line in lines:
        if re.search(r"\(pag\.\s*\d+\s*\)", line, re.I):
            kept.append(line)
            empty_run = 0
            continue
        if not line.strip():
            empty_run += 1
            if empty_run > 4 and kept:
                break
            continue
        if kept and not re.match(r"^\s*\d", line):
            empty_run += 1
            if empty_run > 2:
                break
        kept.append(line)
    return "\n".join(kept)


def parse_index_entries(full_text: str) -> list[IndexEntry]:
    """Apartados principales del índice: número, título y página."""
    block = _index_block(full_text)
    if not block:
        return []

    entries: list[IndexEntry] = []
    seen_pages: set[int] = set()
    for match in INDEX_LINE.finditer(block):
        number = match.group(1).strip()
        title = re.sub(r"\s+", " ", match.group(2)).strip()
        page = int(match.group(3))
        if page in seen_pages and len(title) < 12:
            continue
        seen_pages.add(page)
        role = classify_heading(title)
        entries.append(IndexEntry(number=number, title=title, page=page, role=role))

    entries.sort(key=lambda item: item.page)
    return _dedupe_by_page(entries)


def _dedupe_by_page(entries: list[IndexEntry]) -> list[IndexEntry]:
    merged: list[IndexEntry] = []
    for entry in entries:
        if merged and merged[-1].page == entry.page:
            if len(entry.title) > len(merged[-1].title):
                merged[-1] = entry
            continue
        merged.append(entry)
    return merged


def top_level_index_entries(entries: list[IndexEntry]) -> list[IndexEntry]:
    """Solo apartados de primer nivel (1., 2., …) excluyendo bibliografía y anexos."""
    top: list[IndexEntry] = []
    for entry in entries:
        if "." in entry.number:
            continue
        if entry.is_bibliography:
            continue
        if re.search(r"(?i)^anexo", entry.title):
            continue
        top.append(entry)
    return top


def bibliography_index_entry(entries: list[IndexEntry]) -> IndexEntry | None:
    for entry in entries:
        if entry.is_bibliography:
            return entry
    return None
