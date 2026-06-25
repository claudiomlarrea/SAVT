"""Extracción de apartados principales (1., 2., 3., …) desde el índice del documento."""

from __future__ import annotations

import re
from dataclasses import dataclass

from savt.section_resolver import classify_heading

CONTENT_INDEX_START = re.compile(
    r"(?i)índice\s+de\s+contenido|tabla\s+de\s+contenido",
)
CONTENT_INDEX_END = re.compile(
    r"(?i)índice\s+de\s+figuras|índice\s+de\s+tablas|índice\s+de\s+gráficas",
)
INDEX_HEADING = re.compile(
    r"(?im)^\s*ÍNDICE\s*$|^\s*INDICE\s*$|^\s*TABLA DE CONTENIDO\s*$",
)
_PAGE_IN_PARENS = r"(?:pag\.?|pág\.?|p\.)\s*(\d+)"
INDEX_LINE_PAREN = re.compile(
    rf"(?m)^\s*(\d{{1,2}})(?:\.(?![0-9])|\s+)\s*(.+?)\s*\({_PAGE_IN_PARENS}\s*\)",
    re.IGNORECASE,
)
# Apartado principal: «2. ESTADO DEL ARTE … XXIII» (no 2.1. subapartados).
TOP_LEVEL_LINE = re.compile(
    r"(?m)^\s*(\d{1,2})\.(?!\d)\s*(.+?)\s*(?:[.\u2026…]{2,})\s*([IVXLCDM]+|\d{1,4})\s*$",
    re.IGNORECASE,
)
BIBLIOGRAPHY_TITLE = re.compile(r"(?i)bibliograf|referencias\s+bibliogr|referencias\s*$")
_ROMAN = re.compile(r"^[IVXLCDM]+$", re.I)


@dataclass(frozen=True)
class IndexEntry:
    number: str
    title: str
    page: int
    role: str | None = None
    page_label: str = ""
    page_is_roman: bool = False

    @property
    def is_bibliography(self) -> bool:
        return bool(BIBLIOGRAPHY_TITLE.search(self.title))


def roman_to_int(value: str) -> int:
    value = value.upper().strip()
    if not value or not _ROMAN.match(value):
        return 0
    numerals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(value):
        current = numerals.get(ch, 0)
        if current < prev:
            total -= current
        else:
            total += current
        prev = current
    return total


def _parse_page_token(token: str) -> tuple[int, str, bool]:
    token = token.strip()
    if _ROMAN.match(token):
        return roman_to_int(token), token.upper(), True
    if token.isdigit():
        return int(token), token, False
    return 0, token, False


def _fix_orphan_index_titles(block: str) -> str:
    """Reasigna número cuando el PDF parte «2.» y el título en la línea siguiente."""
    lines = block.splitlines()
    result: list[str] = []
    pending_number: str | None = None
    for line in lines:
        stripped = line.strip()
        only_num = re.match(r"^(\d{1,2})\.$", stripped)
        if only_num:
            pending_number = only_num.group(1)
            continue
        if pending_number and not re.match(r"^\d", stripped):
            if re.search(r"(?:[.\u2026…]{2,})\s*[IVXLCDM]+\s*$", stripped, re.I):
                result.append(f"{pending_number}. {stripped}")
                pending_number = None
                continue
        pending_number = None
        result.append(line)
    return "\n".join(result)


def _normalize_index_lines(block: str) -> str:
    """Une líneas partidas por el PDF: «3.» en una línea y el título en la siguiente."""
    lines = block.splitlines()
    merged: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if re.match(r"^\d{1,2}\.$", line) and idx + 1 < len(lines):
            nxt = lines[idx + 1].strip()
            if not re.match(r"^\d{1,2}\.$", nxt):
                merged.append(f"{line} {nxt}")
                idx += 2
                continue
        merged.append(line)
        idx += 1
    return "\n".join(merged)


def _index_block(full_text: str) -> str:
    """Recorta el bloque del índice de contenido (no figuras/tablas)."""
    head = full_text[: min(len(full_text), 45000)]

    candidates: list[tuple[int, str]] = []
    for start_match in CONTENT_INDEX_START.finditer(head):
        tail = head[start_match.end() : start_match.end() + 22000]
        end_match = CONTENT_INDEX_END.search(tail)
        chunk = tail[: end_match.start()] if end_match else tail[:18000]
        normalized = _normalize_index_lines(chunk)
        score = len(TOP_LEVEL_LINE.findall(normalized))
        score += len(re.findall(r"(?m)^\s*\d{1,2}\.(?!\d)", normalized))
        if score >= 2:
            candidates.append((score, normalized))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return _strip_subsections(
            _fix_orphan_index_titles(candidates[0][1])
        )

    # Formato «(pag. N)» (tesis UCCuyo y similares).
    match = INDEX_HEADING.search(head)
    if match:
        chunk = head[match.end() : match.end() + 12000]
    else:
        first_pag = re.search(rf"\({_PAGE_IN_PARENS}\s*\)", head, re.I)
        if not first_pag or first_pag.start() > 8000:
            return ""
        chunk = head[max(0, first_pag.start() - 4000) : first_pag.start() + 8000]

    lines = chunk.splitlines()
    kept: list[str] = []
    empty_run = 0
    for line in lines:
        if re.search(rf"\({_PAGE_IN_PARENS}\s*\)", line, re.I):
            kept.append(line)
            empty_run = 0
            continue
        if TOP_LEVEL_LINE.search(line) or re.search(r"\.{2,}\s*[IVXLCDM]+\s*$", line, re.I):
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
    return _strip_subsections(
        _fix_orphan_index_titles(_normalize_index_lines("\n".join(kept)))
    )


def _strip_subsections(block: str) -> str:
    top_lines: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d{1,2}\.\d", stripped):
            continue
        if re.match(r"^Figura\s+\d", stripped, re.I):
            break
        top_lines.append(stripped)
    return "\n".join(top_lines)


def _entry_from_match(number: str, title: str, page_token: str) -> IndexEntry | None:
    title = re.sub(r"\s+", " ", title).strip().rstrip(".")
    if len(title) < 3:
        return None
    page, label, is_roman = _parse_page_token(page_token)
    if page <= 0 and not is_roman:
        return None
    if page <= 0:
        page = 1
    role = classify_heading(title)
    return IndexEntry(
        number=number.strip(),
        title=title,
        page=page,
        role=role,
        page_label=label,
        page_is_roman=is_roman,
    )


def parse_index_entries(full_text: str) -> list[IndexEntry]:
    """Apartados del índice: número, título y página (arábiga o romana)."""
    block = _index_block(full_text)
    if not block:
        return []

    entries: list[IndexEntry] = []
    seen: set[tuple[str, str]] = set()

    for pattern in (INDEX_LINE_PAREN, TOP_LEVEL_LINE):
        for match in pattern.finditer(block):
            number = match.group(1).strip()
            if "." in number:
                continue
            title = match.group(2)
            page_token = match.group(3)
            key = (number, title[:40].upper())
            if key in seen:
                continue
            entry = _entry_from_match(number, title, page_token)
            if entry:
                seen.add(key)
                entries.append(entry)

    entries.sort(key=lambda item: (int(item.number) if item.number.isdigit() else 99, item.page))

    # PDF partido: «1.» seguido de «2. ESTADO DEL ARTE» sin línea de introducción.
    if entries and entries[0].number != "1" and entries[0].number.isdigit():
        first_page = 1
        if int(entries[0].number) >= 2:
            entries.insert(
                0,
                IndexEntry(
                    number="1",
                    title="INTRODUCCIÓN",
                    page=first_page,
                    role="introduccion",
                    page_label="I",
                    page_is_roman=True,
                ),
            )

    return _dedupe_by_number(entries)


def _dedupe_by_number(entries: list[IndexEntry]) -> list[IndexEntry]:
    merged: list[IndexEntry] = []
    seen_numbers: set[str] = set()
    for entry in entries:
        if entry.number in seen_numbers:
            continue
        seen_numbers.add(entry.number)
        merged.append(entry)
    return merged


def top_level_index_entries(entries: list[IndexEntry]) -> list[IndexEntry]:
    """Solo apartados de primer nivel (1, 2, 3…) excluyendo bibliografía y anexos."""
    top: list[IndexEntry] = []
    for entry in entries:
        if not entry.number.isdigit():
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
