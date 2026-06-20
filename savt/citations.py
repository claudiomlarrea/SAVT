from __future__ import annotations

import re

from savt.bibliography_styles import apa_keys_match, topical_match
from savt.models import Finding, ReferenceEntry

GENERIC_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "were",
    "have",
    "has",
    "como",
    "para",
    "sobre",
    "entre",
    "desde",
    "hacia",
    "pacientes",
    "estudios",
    "evidencia",
    "resultados",
}


def topical_score(reference: ReferenceEntry, paragraph: str, keywords: list[str]) -> float:
    ref_topical = topical_match(reference, keywords)
    para_tokens = {
        w
        for w in re.findall(r"[a-záéíóúñ]{4,}", paragraph.lower())
        if w not in GENERIC_STOPWORDS
    }
    ref_tokens = {
        w
        for w in re.findall(r"[a-záéíóúñ]{4,}", reference.raw.lower())
        if w not in GENERIC_STOPWORDS
    }
    overlap = len(para_tokens & ref_tokens) / max(len(para_tokens), 1) if para_tokens and ref_tokens else 0.0
    keyword_bonus = 0.35 if ref_topical else 0.0
    return min(1.0, overlap + keyword_bonus)


def _topic_keywords(parsed: dict) -> list[str]:
    return parsed.get("topic_keywords") or []


def is_reference_topical(reference: ReferenceEntry, keywords: list[str]) -> bool:
    return topical_match(reference, keywords)


def _audit_numbered_citations(parsed: dict, keywords: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    bibliography: dict[int, ReferenceEntry] = parsed["bibliography"]
    cited: set[int] = parsed["cited_numbers"]
    body = parsed["body"]

    bib_nums = set(bibliography.keys())
    expected = set(range(1, max(bib_nums) + 1))
    gaps = sorted(expected - bib_nums)
    if gaps:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="error",
                title="Numeración bibliográfica no consecutiva",
                detail=f"Faltan referencias en la secuencia: {gaps[:15]}",
                evidence=f"Última referencia detectada: {max(bib_nums)}",
            )
        )

    missing_in_bib = sorted(cited - bib_nums)
    if missing_in_bib:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="error",
                title="Citas sin entrada bibliográfica",
                detail=f"Referencias citadas en el texto pero ausentes en bibliografía: {missing_in_bib[:20]}",
            )
        )

    uncited = sorted(bib_nums - cited)
    if uncited:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="warning",
                title="Referencias bibliográficas no citadas",
                detail=f"Entradas en bibliografía que no aparecen en el cuerpo: {uncited[:20]}",
            )
        )
    else:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="ok",
                title="Correspondencia citas ↔ bibliografía",
                detail="Todas las referencias numeradas fueron citadas al menos una vez.",
            )
        )

    mismatches: list[str] = []
    for ref_num, paragraph in parsed.get("citation_contexts", []):
        ref = bibliography.get(ref_num)
        if not ref:
            continue
        score = topical_score(ref, paragraph, keywords)
        if score < 0.08 and not is_reference_topical(ref, keywords):
            snippet = paragraph[:160].replace("\n", " ")
            mismatches.append(f"[{ref_num}] score={score:.2f} → …{snippet}…")

    if mismatches:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="warning",
                title="Posible desajuste cita ↔ contenido del párrafo",
                detail="Algunas citas numeradas parecen poco relacionadas con el párrafo donde aparecen.",
                evidence="\n".join(mismatches[:8]),
            )
        )

    return findings


def _audit_apa_citations(parsed: dict, keywords: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    bibliography: dict[int, ReferenceEntry] = parsed["bibliography"]
    cited_keys: set[str] = parsed.get("cited_keys", set())
    bib_keys = {ref.key for ref in bibliography.values() if ref.key}

    missing_in_bib = sorted(key for key in cited_keys if not apa_keys_match(key, bib_keys))
    if missing_in_bib:
        pass  # Detalle completo en bibliography_analysis.py

    uncited = sorted(key for key in bib_keys if not any(apa_keys_match(key, {cited}) for cited in cited_keys))
    if uncited and len(uncited) > len(bib_keys) * 0.35:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="warning",
                title="Muchas referencias APA no detectadas como citadas",
                detail=(
                    f"{len(uncited)} entradas no fueron reconocidas en el texto. "
                    "En PDF es común por cortes de línea o citas narrativas."
                ),
                evidence=", ".join(uncited[:12]),
            )
        )
    elif bib_keys and cited_keys:
        coverage = sum(1 for key in cited_keys if apa_keys_match(key, bib_keys)) / max(len(cited_keys), 1)
        findings.append(
            Finding(
                module="Bibliografía",
                severity="ok",
                title="Correspondencia citas APA ↔ bibliografía",
                detail=(
                    f"Se detectaron {len(cited_keys)} claves autor-año en el texto y "
                    f"{len(bibliography)} referencias bibliográficas "
                    f"(coincidencia directa: {coverage:.0%})."
                ),
            )
        )

    return findings


def audit_citations(parsed: dict) -> list[Finding]:
    findings: list[Finding] = []
    bibliography: dict[int, ReferenceEntry] = parsed["bibliography"]
    body = parsed["body"]
    style = parsed.get("citation_style", "numbered")
    keywords = _topic_keywords(parsed)

    if not bibliography:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="error",
                area="Bibliografía",
                title="No se detectó bibliografía",
                detail="No se encontró una sección BIBLIOGRAFÍA parseable al final del documento.",
                why="Sin bibliografía no es posible verificar trazabilidad académica.",
                how_to_fix="Agregue una sección final titulada BIBLIOGRAFÍA con referencias completas.",
            )
        )
        return findings

    if style == "apa":
        findings.extend(_audit_apa_citations(parsed, keywords))
    else:
        findings.extend(_audit_numbered_citations(parsed, keywords))

    duplicate_dois: dict[str, list[int]] = {}
    for num, ref in bibliography.items():
        if ref.doi:
            duplicate_dois.setdefault(ref.doi.lower(), []).append(num)
    dupes = {doi: nums for doi, nums in duplicate_dois.items() if len(nums) > 1}
    if dupes:
        sample = ", ".join(f"{doi} → refs {nums}" for doi, nums in list(dupes.items())[:5])
        findings.append(
            Finding(
                module="Bibliografía",
                severity="warning",
                title="DOI duplicados",
                detail="Se detectaron DOI repetidos en distintas referencias.",
                evidence=sample,
            )
        )

    if style == "numbered":
        irrelevant_refs = [
            n for n, ref in bibliography.items() if not is_reference_topical(ref, keywords)
        ]
        if irrelevant_refs and len(irrelevant_refs) > len(bibliography) * 0.15:
            pass  # Detalle en bibliography_analysis.py

    return findings
