from __future__ import annotations

import re


def collapse_soft_line_breaks(text: str) -> str:
    """Une saltos de línea internos típicos de PDF sin perder párrafos."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    merged: list[str] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer:
            merged.append(buffer.strip())
            buffer = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            merged.append("")
            continue
        if not buffer:
            buffer = stripped
            continue
        if re.match(r"^\d+\.", stripped):
            flush()
            buffer = stripped
            continue
        if buffer.endswith("-") and stripped[:1].islower():
            buffer = buffer[:-1] + stripped
            continue
        if buffer.endswith((".", "?", "!", ":", ";")):
            flush()
            buffer = stripped
            continue
        if re.match(r"^[(\[]", stripped) or re.match(r"^[a-záéíóúñ]", stripped):
            buffer = f"{buffer} {stripped}"
            continue
        if len(buffer) < 80 and not buffer.endswith("."):
            buffer = f"{buffer} {stripped}"
            continue
        flush()
        buffer = stripped
    flush()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(merged))


def normalize_bibliography_text(bib_text: str) -> str:
    """Prepara bibliografía extraída de PDF para parseo APA/numerado."""
    if not bib_text:
        return bib_text
    text = collapse_soft_line_breaks(bib_text)
    text = re.sub(
        r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñ.\-&\s]{1,80}\.)\s+\((\d{4}[a-z]?)\)",
        r"\1 (\2)",
        text,
    )
    # Autor en una línea y (AAAA) en la siguiente — habitual en PDF.
    text = re.sub(r"([A-Z]\.)\s*\n\s*\((\d{4})", r"\1 (\2", text)
    # Apellidos partidos por salto de línea: Roger-\nMartínez → Roger-Martínez
    text = re.sub(r"-\s*\n\s*", "-", text)
    text = re.sub(r"https?://doi\.org/https?://doi\.org/", "https://doi.org/", text, flags=re.I)
    text = re.sub(r"doi\.org/(https?://doi\.org/)", "doi.org/", text, flags=re.I)
    # URL partida en guion + número de referencia con autor en la línea siguiente.
    text = re.sub(
        r"([/\w])-(\d+\.\s*(?:\n\s*)?[A-ZÁÉÍÓÚ][^\n]{3,120}?,\s)",
        r"\1-\n\2",
        text,
    )
    return text


def normalize_full_document_text(text: str) -> str:
    return collapse_soft_line_breaks(text)
