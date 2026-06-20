from __future__ import annotations

import re
from collections import Counter

from savt.models import Finding

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
    # Plantillas de encuesta con opciones repetidas.
    if lower.count("totalmente de acuerdo") >= 2 or lower.count("nada de acuerdo") >= 2:
        return True
    return False


def audit_similarity(parsed: dict) -> list[Finding]:
    findings: list[Finding] = []
    paragraphs = [p.strip() for p in parsed["body"].split("\n\n") if len(p.split()) > 40]

    duplicated: list[str] = []
    seen: dict[str, str] = {}
    for paragraph in paragraphs:
        if _is_boilerplate_paragraph(paragraph):
            continue
        normalized = re.sub(r"\s+", " ", paragraph.lower())
        normalized = re.sub(r"\(\d+(?:[,\s\-–]\d+)*\)", "", normalized)
        if len(normalized) < 120:
            continue
        if normalized in seen:
            duplicated.append(paragraph[:140] + "…")
        else:
            seen[normalized] = paragraph

    if duplicated:
        findings.append(
            Finding(
                module="Similitud",
                severity="warning",
                title="Párrafos duplicados o casi idénticos",
                detail="Se detectaron repeticiones literales dentro del documento.",
                evidence="\n".join(duplicated[:5]),
                why="La repetición interna debilita la coherencia y puede confundir al evaluador.",
                how_to_fix="Unifique párrafos repetidos o reformule para evitar redundancia.",
            )
        )

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

    if not duplicated:
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
