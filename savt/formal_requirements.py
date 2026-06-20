from __future__ import annotations

import re

from savt.audit_config import AuditConfig
from savt.document_sections import assess_cover, extract_abstract, extract_title
from savt.institutional_profiles import InstitutionalProfile
from savt.models import Finding


def audit_formal_requirements(parsed: dict, profile: InstitutionalProfile) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    full_text = parsed.get("full_text") or parsed.get("body", "")
    checks: dict[str, bool | str | int] = {}

    cover = assess_cover(full_text)
    cover_score = sum(1 for ok in cover.values() if ok)
    checks["portada_completa"] = cover_score >= 3
    checks.update({f"portada_{k}": v for k, v in cover.items()})

    if cover_score < 3:
        missing = [k for k, ok in cover.items() if not ok]
        findings.append(
            Finding(
                module="Normativa",
                severity="warning" if cover_score < 2 else "info",
                title="Portada incompleta o no detectada",
                detail=(
                    f"Elementos no detectados en las primeras páginas: {', '.join(missing)}. "
                    "Verifique portada según normativa de su universidad."
                ),
                why="La portada es requisito formal en evaluaciones de grado y posgrado.",
                how_to_fix=(
                    "Incluya institución, título, autor/a, director/a y carrera o programa."
                ),
            )
        )
    else:
        findings.append(
            Finding(
                module="Normativa",
                severity="ok",
                title="Portada detectada con elementos principales",
                detail="Se identificaron institución, título, director/a y autor/a.",
            )
        )

    lower = full_text.lower()
    index_ok = bool(re.search(r"\b(índice|indice|table of contents)\b", lower[:12000]))
    checks["indice"] = index_ok
    if not index_ok:
        findings.append(
            Finding(
                module="Normativa",
                severity="info",
                title="Índice general no detectado",
                detail="No se encontró un índice general al inicio del documento.",
                why="El índice facilita la evaluación del jurado.",
                how_to_fix="Genere índice automático con capítulos y subsecciones numeradas.",
            )
        )

    fig_index = bool(re.search(r"índice de figuras|indice de figuras|list of figures", lower[:15000]))
    tab_index = bool(re.search(r"índice de tablas|indice de tablas|list of tables", lower[:15000]))
    checks["indice_figuras"] = fig_index
    checks["indice_tablas"] = tab_index

    abstract_text, abstract_words, abstract_kind = extract_abstract(full_text)
    checks["abstract_words"] = abstract_words
    checks["abstract_kind"] = abstract_kind
    checks["abstract_text_preview"] = abstract_text[:200] if abstract_text else ""
    checks["document_title"] = extract_title(full_text, parsed.get("filename", ""))

    if abstract_words == 0:
        findings.append(
            Finding(
                module="Normativa",
                severity="info",
                title="Resumen o abstract no detectado con encabezado estándar",
                detail=(
                    "No se encontró RESUMEN, ABSTRACT ni sección equivalente "
                    "(p. ej. Presentación del Trabajo). Verifique la normativa de su casa de estudios."
                ),
                why="La mayoría de universidades exigen un resumen estructurado.",
                how_to_fix=(
                    "Agregue resumen con problema, objetivos, metodología y resultados principales."
                ),
            )
        )
    elif abstract_words > profile.abstract_max_words:
        findings.append(
            Finding(
                module="Normativa",
                severity="warning",
                title="Resumen excede extensión recomendada",
                detail=(
                    f"Sección '{abstract_kind}' detectada: ~{abstract_words} palabras "
                    f"(máx. sugerido {profile.abstract_max_words} para {profile.label})."
                ),
                how_to_fix="Condense el resumen manteniendo problema, método y hallazgos clave.",
            )
        )
    elif abstract_words < profile.abstract_min_words:
        findings.append(
            Finding(
                module="Normativa",
                severity="info",
                title="Resumen breve",
                detail=(
                    f"Sección '{abstract_kind}' detectada: ~{abstract_words} palabras "
                    f"(mín. sugerido {profile.abstract_min_words})."
                ),
                how_to_fix="Amplíe el resumen con objetivos, metodología y resultados principales.",
            )
        )
    else:
        findings.append(
            Finding(
                module="Normativa",
                severity="ok",
                title="Resumen dentro de extensión esperada",
                detail=f"Sección '{abstract_kind}' detectada: ~{abstract_words} palabras.",
            )
        )

    keywords_ok = bool(
        re.search(r"palabras?\s+clave|keywords", lower[:15000], re.IGNORECASE)
    )
    checks["palabras_clave"] = keywords_ok
    if abstract_words > 0 and not keywords_ok:
        findings.append(
            Finding(
                module="Normativa",
                severity="info",
                title="Palabras clave no detectadas",
                detail="No se encontró sección de palabras clave junto al resumen.",
                how_to_fix="Incluya 3–5 palabras clave descriptoras del tema bajo el resumen.",
            )
        )

    style = parsed.get("citation_style", "")
    if profile.citation_style != "any" and style and style != profile.citation_style:
        findings.append(
            Finding(
                module="Normativa",
                severity="info",
                title="Estilo de citación distinto al sugerido para el nivel",
                detail=(
                    f"Perfil {profile.label} sugiere {profile.citation_style.upper()}; "
                    f"detectado: {style.upper()}."
                ),
                how_to_fix=f"Confirme con su director el estilo de citación requerido.",
            )
        )

    ref_count = len(parsed.get("bibliography") or {})
    checks["reference_count"] = ref_count
    if ref_count < profile.min_references:
        findings.append(
            Finding(
                module="Normativa",
                severity="warning",
                title="Bibliografía por debajo del mínimo sugerido",
                detail=(
                    f"{ref_count} referencias detectadas; mínimo sugerido para "
                    f"{profile.label}: {profile.min_references}."
                ),
                why="La profundidad bibliográfica es criterio habitual en jurados de posgrado.",
                how_to_fix="Amplíe revisión de literatura con fuentes actuales y pertinentes.",
            )
        )

    return findings, checks


def run_formal_audit(parsed: dict, config: AuditConfig) -> tuple[list[Finding], dict]:
    if not config.check_formal:
        return [], {}
    return audit_formal_requirements(parsed, config.profile)
