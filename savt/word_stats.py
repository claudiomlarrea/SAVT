"""Conteo de palabras total y por apartados detectados en la tesis."""

from __future__ import annotations

import re

from savt.document_sections import get_section_map
from savt.section_resolver import discover_headings

ROLE_LABELS: dict[str, str] = {
    "presentacion": "Presentación / resumen",
    "introduccion": "Introducción",
    "marco_teorico": "Marco teórico",
    "metodologia": "Metodología",
    "resultados": "Resultados",
    "discusion": "Discusión",
    "conclusiones": "Conclusiones",
    "objetivos": "Objetivos",
}

_SKIP_HEADING = re.compile(r"\b(BIBLIOGRAF[IÍ]A|REFERENCIAS|ANEXOS?)\b", re.I)


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or "", re.UNICODE))


def build_word_statistics(parsed: dict) -> dict:
    body = parsed.get("body", "")
    total_body = parsed.get("word_count") or count_words(body)
    bib_words = parsed.get("bibliography_word_count", 0)

    sections: list[dict] = []
    headings = discover_headings(body)

    for heading in headings:
        if _SKIP_HEADING.search(heading.title):
            continue
        chunk = body[heading.start + len(heading.title) : heading.end].strip()
        words = count_words(chunk)
        if re.search(r"\b(PARTE|CAPÍTULO|CAPITULO|TOMO)\b", heading.title, re.I) and words < 50:
            continue
        if words < 25 and not heading.role:
            continue
        sections.append(
            {
                "title": heading.title.strip()[:120],
                "words": words,
                "role": heading.role or "",
                "role_label": ROLE_LABELS.get(heading.role, "") if heading.role else "",
            }
        )

    if not sections:
        section_map = parsed.get("section_map") or get_section_map(body)
        for role, text in section_map.items():
            sections.append(
                {
                    "title": ROLE_LABELS.get(role, role.replace("_", " ").title()),
                    "words": count_words(text),
                    "role": role,
                    "role_label": ROLE_LABELS.get(role, ""),
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
    }
