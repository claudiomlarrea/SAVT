"""Conteo de palabras total y por apartados canónicos de la tesis."""

from __future__ import annotations

import re

from savt.document_sections import get_section_map


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or "", re.UNICODE))


# Orden de presentación y etiquetas para la tabla agregada.
CANONICAL_SECTION_ORDER: tuple[tuple[str, str], ...] = (
    ("presentacion", "Presentación / resumen"),
    ("introduccion", "Introducción"),
    ("objetivos", "Objetivos"),
    ("marco_teorico", "Marco teórico y estado del arte"),
    ("metodologia", "Metodología"),
    ("resultados", "Resultados"),
    ("discusion", "Discusión"),
    ("conclusiones", "Conclusiones"),
)


def _canonical_word_map(parsed: dict) -> dict[str, str]:
    body = parsed.get("body", "")
    return parsed.get("section_map") or get_section_map(body)


def build_word_statistics(parsed: dict) -> dict:
    body = parsed.get("body", "")
    total_body = parsed.get("word_count") or count_words(body)
    bib_words = parsed.get("bibliography_word_count", 0)
    role_texts = _canonical_word_map(parsed)

    sections: list[dict] = []
    classified_words = 0

    for role, label in CANONICAL_SECTION_ORDER:
        text = role_texts.get(role, "")
        words = count_words(text)
        if words <= 0:
            continue
        classified_words += words
        sections.append(
            {
                "title": label,
                "words": words,
                "role": role,
                "role_label": label,
            }
        )

    other_words = max(0, total_body - classified_words)
    if other_words >= 50:
        sections.append(
            {
                "title": "Otros apartados (anexos, índices, material no clasificado)",
                "words": other_words,
                "role": "otros",
                "role_label": "Otros",
            }
        )

    total_for_pct = max(total_body, 1)
    for item in sections:
        pct = round(item["words"] * 100 / total_for_pct, 1)
        item["percent"] = pct
        item["percent_label"] = f"{pct:.1f}%"

    return {
        "total_body_words": total_body,
        "bibliography_words": bib_words,
        "sections": sections,
        "classified_body_words": classified_words,
    }
