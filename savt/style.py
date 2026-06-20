from __future__ import annotations

import re
from collections import Counter

from savt.audit_config import AuditConfig
from savt.models import Finding

COLLOQUIAL_PATTERNS = [
    r"\bun montón\b",
    r"\bok\b",
    r"\bgenial\b",
]


def _terminology_variants(body: str, topic_keywords: list[str]) -> dict[str, int]:
    """Detecta variantes terminológicas a partir de palabras clave del tema."""
    counts: dict[str, int] = {}
    for kw in topic_keywords[:6]:
        if len(kw) < 5:
            continue
        pattern = re.escape(kw)
        count = len(re.findall(pattern, body, re.IGNORECASE))
        if count >= 3:
            counts[kw] = count
    return counts


def audit_style(parsed: dict, config: AuditConfig | None = None) -> list[Finding]:
    findings: list[Finding] = []
    body = parsed["body"]
    lower = body.lower()
    config = config or AuditConfig()

    future_in_past_sections = []
    if re.search(r"1\.3 Justificación", body, re.IGNORECASE):
        intro = re.search(r"1\.3 Justificación(.+?)1\.4", body, re.IGNORECASE | re.DOTALL)
        if intro and re.search(r"\b(contribuirán|podrán|permitirá)\b", intro.group(1), re.IGNORECASE):
            future_in_past_sections.append("Justificación usa futuro para un trabajo ya concluido.")

    if future_in_past_sections:
        findings.append(
            Finding(
                module="Estilo",
                severity="info",
                title="Mezcla de tiempos verbales en introducción",
                detail=" ".join(future_in_past_sections),
            )
        )

    repeated_starts = Counter()
    for paragraph in body.split("\n\n"):
        paragraph = paragraph.strip()
        if len(paragraph) < 80:
            continue
        first_words = " ".join(paragraph.split()[:3]).lower()
        repeated_starts[first_words] += 1
    overused = [k for k, v in repeated_starts.items() if v >= 8]
    if overused:
        findings.append(
            Finding(
                module="Estilo",
                severity="info",
                title="Inicios de párrafo repetitivos",
                detail="Algunos párrafos comienzan con la misma fórmula léxica.",
                evidence=", ".join(overused[:6]),
            )
        )

    topic_kw = parsed.get("topic_keywords") or []
    term_counts = _terminology_variants(body, topic_kw)
    if len(term_counts) >= 2:
        findings.append(
            Finding(
                module="Estilo",
                severity="ok",
                title="Terminología clave presente en el documento",
                detail=f"Términos del tema detectados: {list(term_counts.keys())[:5]}",
            )
        )

    short_paragraphs = sum(1 for p in body.split("\n\n") if 0 < len(p.split()) < 25)
    if short_paragraphs > 20:
        findings.append(
            Finding(
                module="Estilo",
                severity="info",
                title="Abundancia de párrafos breves",
                detail=f"Se detectaron {short_paragraphs} párrafos con menos de 25 palabras.",
            )
        )

    colloquial_hits = []
    for pattern in COLLOQUIAL_PATTERNS:
        if re.search(pattern, lower):
            colloquial_hits.append(pattern)
    if colloquial_hits:
        findings.append(
            Finding(
                module="Estilo",
                severity="info",
                title="Posibles expresiones coloquiales",
                detail="Revisar tono académico en expresiones informales.",
                evidence=", ".join(colloquial_hits),
            )
        )

    page_estimate = parsed["page_estimate"]
    body_only = parsed.get("page_estimate_body_only", page_estimate)
    min_target = config.effective_min_pages
    max_target = config.effective_max_pages
    profile_label = config.profile.label

    if page_estimate < min_target:
        findings.append(
            Finding(
                module="Extensión",
                severity="warning",
                title="Extensión por debajo del rango objetivo",
                detail=(
                    f"Estimación total ~{page_estimate} páginas (< {min_target} para {profile_label}). "
                    f"Cuerpo ~{body_only} páginas."
                ),
                why="La extensión es criterio en rúbricas UNCUyo, UCCuyo y CONEAU.",
                how_to_fix="Amplíe marco teórico, discusión o conclusiones según indicaciones de su director.",
            )
        )
    elif page_estimate > max_target:
        findings.append(
            Finding(
                module="Extensión",
                severity="info",
                title="Extensión por encima del rango objetivo configurado",
                detail=(
                    f"Estimación total ~{page_estimate} páginas (> {max_target} para {profile_label}). "
                    "En tesis empíricas de posgrado esto puede ser normal."
                ),
            )
        )
    else:
        findings.append(
            Finding(
                module="Extensión",
                severity="ok",
                title="Extensión dentro del rango esperado",
                detail=(
                    f"Estimación total ~{page_estimate} páginas "
                    f"(cuerpo ~{body_only}; rango {min_target}–{max_target})."
                ),
            )
        )

    return findings
