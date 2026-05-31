from __future__ import annotations

import re
from collections import Counter

from savt.models import Finding


def audit_similarity(parsed: dict) -> list[Finding]:
    findings: list[Finding] = []
    paragraphs = [p.strip() for p in parsed["body"].split("\n\n") if len(p.split()) > 40]

    duplicated: list[str] = []
    seen: dict[str, str] = {}
    for paragraph in paragraphs:
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
            )
        )

    sentence_starts = Counter()
    for paragraph in paragraphs:
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
