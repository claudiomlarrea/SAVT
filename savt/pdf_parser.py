from __future__ import annotations

import io
import re
from typing import BinaryIO

import fitz

from savt.parser import _normalize


def _read_bytes(source: BinaryIO | str) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, str):
        with open(source, "rb") as handle:
            return handle.read()
    source.seek(0)
    return source.read()


def extract_text_from_pdf(source: BinaryIO | str) -> tuple[str, int]:
    data = _read_bytes(source)
    document = fitz.open(stream=data, filetype="pdf")
    pages: list[str] = []
    for page in document:
        pages.append(page.get_text("text"))
    return "\n".join(pages), document.page_count


def remove_pdf_toc_lines(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if re.search(r"\.{4,}\s*\d+\s*$", stripped):
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        cleaned_lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines))


def remove_pdf_front_matter(body: str) -> str:
    """Recorta portada, índice y metadatos previos al inicio del cuerpo argumental."""
    markers = [
        # PDF: el encabezado suele ir en la misma línea que el primer párrafo.
        r"(?im)(?:^|\n)\s*INTRODUCCI[ÓO]N\b",
        r"1\.\s+Planteamiento general\s*\n",
        r"1\.1\s+Presentaci[oó]n del tema\s*\n",
        r"CAPÍTULO I\.\s*INTRODUCCIÓN\s*\n",
        r"1\.\s+Introducci[oó]n\s*\n",
        r"(?m)^INTRODUCCI[ÓO]N\s*\n",
        r"Presentaci[oó]n del Trabajo(?: de Tesis| Final)?\s*\n",
    ]
    for pattern in markers:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return body[match.start() :].strip()
    for pattern in (
        r"(?im)(?:^|\n)\s*2\.\s*Pregunta de investigaci",
        r"(?im)(?:^|\n)\s*1\.\s+[A-ZÁÉÍÓÚÑ]",
    ):
        match = re.search(pattern, body)
        if match and match.start() > 800:
            return body[match.start() :].strip()
    return body


def prepare_pdf_text(source: BinaryIO | str) -> tuple[str, int]:
    raw_text, page_count = extract_text_from_pdf(source)
    cleaned = remove_pdf_toc_lines(raw_text)
    return cleaned, page_count
