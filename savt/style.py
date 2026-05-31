from __future__ import annotations

import re
from collections import Counter

from savt.models import Finding

COLLOQUIAL_PATTERNS = [
    r"\bmuy\b",
    r"\bun montón\b",
    r"\bok\b",
    r"\bgenial\b",
]

TERM_VARIANTS = {
    "diástasis de rectos abdominales": r"diástasis de rectos abdominales",
    "diástasis de rectos": r"diástasis de rectos(?!\s+abdominales)",
    "DRA": r"\bDRA\b",
    "dermolipectomía": r"dermolipectomía",
    "abdominoplastia": r"abdominoplastia",
}


def audit_style(parsed: dict) -> list[Finding]:
    findings: list[Finding] = []
    body = parsed["body"]
    lower = body.lower()

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

    term_counts = {
        label: len(re.findall(pattern, body, re.IGNORECASE))
        for label, pattern in TERM_VARIANTS.items()
    }
    if term_counts["DRA"] > 0 and term_counts["diástasis de rectos abdominales"] > 0:
        findings.append(
            Finding(
                module="Estilo",
                severity="ok",
                title="Terminología clave definida y reutilizada",
                detail=f"Conteos: {term_counts}",
            )
        )
    elif term_counts["diástasis de rectos"] > 5 and term_counts["diástasis de rectos abdominales"] > 5:
        findings.append(
            Finding(
                module="Estilo",
                severity="info",
                title="Variantes terminológicas coexistiendo",
                detail=(
                    "Conviven 'diástasis de rectos' y 'diástasis de rectos abdominales'. "
                    "Definir una forma principal y mantenerla."
                ),
                evidence=str(term_counts),
            )
        )

    if "plication\"0" in body or 'plication"0' in body:
        findings.append(
            Finding(
                module="Estilo",
                severity="error",
                title="Error tipográfico en ecuación de búsqueda",
                detail='Se detectó "rectus plication"0) en metodología.',
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
    is_pdf = parsed.get("file_type") == "pdf"
    min_target = 50 if not is_pdf else 80
    max_target = 80 if not is_pdf else 150

    if page_estimate < min_target:
        findings.append(
            Finding(
                module="Extensión",
                severity="warning",
                title="Extensión por debajo del rango objetivo",
                detail=(
                    f"Estimación total ~{page_estimate} páginas (< {min_target}). "
                    f"Cuerpo ~{body_only} páginas."
                ),
            )
        )
    elif page_estimate > max_target:
        findings.append(
            Finding(
                module="Extensión",
                severity="info" if is_pdf else "warning",
                title="Extensión por encima del rango objetivo configurado",
                detail=(
                    f"Estimación total ~{page_estimate} páginas (> {max_target}). "
                    "En tesis empíricas de maestría/doctorado esto puede ser normal."
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
                    f"(cuerpo ~{body_only})."
                ),
            )
        )

    return findings
