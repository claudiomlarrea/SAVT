"""Normalización del texto extraído por PyMuPDF antes del pipeline documental."""

from __future__ import annotations

import re
from typing import TypedDict


class PdfExtractionNormalization(TypedDict):
    original_pages: list[str]
    normalized_pages: list[str]
    original_text: str
    normalized_text: str


_PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:pág\.?|pag\.?|p\.|page)\s*\d+\s*$|^\s*\d{1,4}\s*$",
    re.IGNORECASE,
)
_ONLY_SECTION_NUMBER = re.compile(r"^\d{1,2}\.$")


def _looks_like_title_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 4:
        return False
    if re.match(r"^\d", stripped):
        return False
    letters = [ch for ch in stripped if ch.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(ch.isupper() for ch in letters) / len(letters)
    return upper_ratio >= 0.55 or stripped[:1].isupper()


def _join_hyphen_line_breaks(text: str) -> str:
    """Une palabras partidas con guión al final de línea (p. ej. «ligno-\\ncelulósica»)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"-\s*\n\s*(?=[a-záéíóúñ])", "", text)


def _join_split_titles(text: str) -> str:
    """Une numeración y título partidos sin fusionar secuencias «1. / 2. / TÍTULO» del índice."""
    lines = text.split("\n")
    merged: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        if _ONLY_SECTION_NUMBER.match(stripped):
            prev_lone = bool(merged) and _ONLY_SECTION_NUMBER.match(merged[-1].strip())
            if prev_lone:
                merged.append(stripped)
                idx += 1
                continue
            if idx + 1 < len(lines):
                nxt = lines[idx + 1].strip()
                if _ONLY_SECTION_NUMBER.match(nxt):
                    merged.append(stripped)
                    idx += 1
                    continue
                if (
                    nxt
                    and _looks_like_title_line(nxt)
                    and not re.match(r"^\d{1,2}\.", nxt)
                ):
                    merged.append(f"{stripped} {nxt}")
                    idx += 2
                    continue

        merged.append(line)
        idx += 1
    return "\n".join(merged)


def _collapse_blank_lines(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text)


def _normalize_spaces(text: str) -> str:
    lines: list[str] = []
    for line in text.split("\n"):
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned)
    return "\n".join(lines)


def _edge_lines(page: str, *, from_top: bool, max_lines: int = 3) -> list[str]:
    lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
    if not lines:
        return []
    if from_top:
        return lines[:max_lines]
    return lines[-max_lines:]


def _strip_repeated_headers_footers(pages: list[str]) -> list[str]:
    """Elimina líneas idénticas repetidas al inicio o fin de varias páginas."""
    if len(pages) < 3:
        return list(pages)

    threshold = max(3, int(len(pages) * 0.35))
    top_counts: dict[str, int] = {}
    bottom_counts: dict[str, int] = {}

    for page in pages:
        seen_top: set[str] = set()
        for line in _edge_lines(page, from_top=True):
            if line in seen_top:
                continue
            seen_top.add(line)
            top_counts[line] = top_counts.get(line, 0) + 1
        seen_bottom: set[str] = set()
        for line in _edge_lines(page, from_top=False):
            if line in seen_bottom:
                continue
            seen_bottom.add(line)
            bottom_counts[line] = bottom_counts.get(line, 0) + 1

    repeated_top = {
        line
        for line, count in top_counts.items()
        if count >= threshold and (len(line) <= 90 or _PAGE_NUMBER_LINE.match(line))
    }
    repeated_bottom = {
        line
        for line, count in bottom_counts.items()
        if count >= threshold and (len(line) <= 90 or _PAGE_NUMBER_LINE.match(line))
    }

    cleaned_pages: list[str] = []
    for page in pages:
        lines = page.splitlines()
        start = 0
        while start < len(lines):
            stripped = lines[start].strip()
            if not stripped:
                start += 1
                continue
            if stripped in repeated_top:
                start += 1
                continue
            break

        end = len(lines)
        while end > start:
            stripped = lines[end - 1].strip()
            if not stripped:
                end -= 1
                continue
            if stripped in repeated_bottom:
                end -= 1
                continue
            break

        cleaned_pages.append("\n".join(lines[start:end]))
    return cleaned_pages


def _normalize_page_text(text: str) -> str:
    text = _join_hyphen_line_breaks(text)
    text = _join_split_titles(text)
    text = _collapse_blank_lines(text)
    text = _normalize_spaces(text)
    return text


def normalize_pdf_extraction(page_texts: list[str]) -> PdfExtractionNormalization:
    """
    Normaliza el texto por página extraído con PyMuPDF.

    Conserva copia original y devuelve páginas normalizadas para el pipeline.
    """
    original_pages = list(page_texts)
    original_text = "\n".join(original_pages)

    stripped_pages = _strip_repeated_headers_footers(original_pages)
    normalized_pages = [_normalize_page_text(page) for page in stripped_pages]
    normalized_text = "\n".join(normalized_pages)

    return {
        "original_pages": original_pages,
        "normalized_pages": normalized_pages,
        "original_text": original_text,
        "normalized_text": normalized_text,
    }
