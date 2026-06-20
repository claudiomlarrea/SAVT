from __future__ import annotations

import re
from collections import Counter

from savt.models import Finding
from savt.page_locator import estimate_page_from_offset, format_pages, iter_paragraphs_with_offset

_ANNEX_MARKERS = re.compile(
    r"\b(anexo|apéndice|apendice|variables?\s+e\s+indicadores|plantilla)\b",
    re.I,
)
_TABLE_ROW_PATTERN = re.compile(r"^\s*\|?.+\|.+\|?\s*$|^\s*\d+[\.\)]\s+\w")


def _is_boilerplate_paragraph(paragraph: str) -> bool:
    lower = paragraph.lower()
    if _ANNEX_MARKERS.search(lower):
        return True
    if _TABLE_ROW_PATTERN.match(paragraph.strip()):
        return True
    if lower.count("totalmente de acuerdo") >= 2 or lower.count("nada de acuerdo") >= 2:
        return True
    return False


def _preview(text: str, max_len: int = 140) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_len:
        return clean
    return clean[:max_len] + "…"


def audit_similarity(parsed: dict) -> list[Finding]:
    findings: list[Finding] = []
    body = parsed.get("body", "")
    occurrences: dict[str, list[tuple[int, str]]] = {}

    for paragraph, offset in iter_paragraphs_with_offset(body):
        if len(paragraph.split()) <= 40 or _is_boilerplate_paragraph(paragraph):
            continue
        normalized = re.sub(r"\s+", " ", paragraph.lower())
        normalized = re.sub(r"\(\d+(?:[,\s\-–]\d+)*\)", "", normalized)
        if len(normalized) < 120:
            continue
        occurrences.setdefault(normalized, []).append((offset, paragraph))

    duplicate_groups: list[dict] = []
    for _norm, hits in occurrences.items():
        if len(hits) < 2:
            continue
        pages = sorted(
            {
                p
                for offset, _ in hits
                if (p := estimate_page_from_offset(body, offset, parsed))
            }
        )
        duplicate_groups.append(
            {
                "pages": pages,
                "pages_label": format_pages(pages),
                "preview": _preview(hits[0][1]),
                "count": len(hits),
            }
        )

    if duplicate_groups:
        lines = []
        for idx, group in enumerate(duplicate_groups[:8], start=1):
            lines.append(
                f"{idx}. {group['pages_label']} ({group['count']} apariciones): «{group['preview']}»"
            )
        findings.append(
            Finding(
                module="Similitud",
                severity="warning",
                title="Párrafos duplicados o casi idénticos",
                detail=(
                    f"Se detectaron {len(duplicate_groups)} bloques de texto repetidos literalmente "
                    "en distintas partes del documento."
                ),
                evidence="\n".join(lines),
                why="La repetición interna debilita la coherencia y puede confundir al evaluador.",
                how_to_fix="Unifique párrafos repetidos o reformule para evitar redundancia.",
            )
        )

    paragraphs = [p for p, _ in iter_paragraphs_with_offset(body) if len(p.split()) > 40]
    sentence_starts = Counter()
    for paragraph in paragraphs:
        if _is_boilerplate_paragraph(paragraph):
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            words = sentence.split()[:4]
            if len(words) >= 3:
                sentence_starts[" ".join(words).lower()] += 1
    boilerplate = [s for s, c in sentence_starts.items() if c >= 6]
    if boilerplate:
        findings.append(
            Finding(
                module="Similitud",
                severity="info",
                title="Patrones repetitivos de redacción",
                detail=(
                    "Puede indicar plantillas, parafraseo insuficiente o redacción asistida. "
                    "No equivale a plagio externo."
                ),
                evidence="; ".join(boilerplate[:5]),
            )
        )

    if not duplicate_groups:
        findings.append(
            Finding(
                module="Similitud",
                severity="info",
                title="Similitud interna básica",
                detail=(
                    "No se detectaron duplicados exactos de párrafos. "
                    "La verificación contra fuentes externas requiere integración futura."
                ),
            )
        )

    return findings
