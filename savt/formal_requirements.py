from __future__ import annotations

import re

from savt.audit_config import AuditConfig
from savt.institutional_profiles import InstitutionalProfile
from savt.models import Finding


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, re.UNICODE))


def _extract_abstract(full_text: str) -> tuple[str, int]:
    patterns = [
        r"(?is)(?:^|\n)\s*RESUMEN\s*\n(.+?)(?:\n\s*(?:PALABRAS?\s+CLAVE|ABSTRACT|ÍNDICE|INDICE|CAPÍTULO|CAPITULO|\d+\.\s))",
        r"(?is)(?:^|\n)\s*ABSTRACT\s*\n(.+?)(?:\n\s*(?:KEYWORDS|PALABRAS?\s+CLAVE|ÍNDICE|INDICE|CAPÍTULO|CAPITULO|\d+\.\s))",
    ]
    for pattern in patterns:
        match = re.search(pattern, full_text)
        if match:
            text = re.sub(r"\s+", " ", match.group(1)).strip()
            if len(text) > 80:
                return text, _word_count(text)
    return "", 0


def audit_formal_requirements(parsed: dict, profile: InstitutionalProfile) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    full_text = parsed.get("full_text") or parsed.get("body", "")
    lower = full_text.lower()
    checks: dict[str, bool | str | int] = {}

    cover_markers = [
        ("universidad", r"\buniversidad\b"),
        ("titulo_tema", r"\btema\s*:|\btítulo\s*:|\btitulo\s*:"),
        ("director", r"\bdirector(?:a)?\s*:"),
        ("estudiante", r"\bestudiante\s*:|tesista|autor(?:a)?\s*:"),
    ]
    cover_found = sum(1 for _, pat in cover_markers if re.search(pat, lower[:4000]))
    checks["portada_completa"] = cover_found >= 3
    if cover_found < 2:
        findings.append(
            Finding(
                module="Normativa",
                severity="warning",
                title="Portada incompleta o no detectada",
                detail=(
                    "No se identificaron claramente universidad, director/a y estudiante en las "
                    "primeras páginas. Verifique portada externa e interna según normativa institucional."
                ),
                why="La portada es requisito formal en rúbricas UNCUyo/UCCuyo y CONEAU.",
                how_to_fix="Incluya portada con institución, carrera, título, director/a, tesista y fecha.",
            )
        )

    index_ok = bool(re.search(r"\b(índice|indice)\b", lower[:8000]))
    checks["indice"] = index_ok
    if not index_ok:
        findings.append(
            Finding(
                module="Normativa",
                severity="info",
                title="Índice general no detectado",
                detail="No se encontró un índice general al inicio del documento.",
                why="El índice facilita la evaluación y es exigencia en rúbricas de grado y posgrado.",
                how_to_fix="Genere índice automático en Word e incluya capítulos y subsecciones numeradas.",
            )
        )

    fig_index = bool(re.search(r"índice de figuras|indice de figuras", lower[:12000]))
    tab_index = bool(re.search(r"índice de tablas|indice de tablas", lower[:12000]))
    checks["indice_figuras"] = fig_index
    checks["indice_tablas"] = tab_index

    abstract_text, abstract_words = _extract_abstract(full_text)
    checks["abstract_words"] = abstract_words
    checks["abstract_text_preview"] = abstract_text[:200] if abstract_text else ""

    if abstract_words == 0:
        findings.append(
            Finding(
                module="Normativa",
                severity="warning",
                title="Resumen o abstract no detectado",
                detail="No se encontró sección RESUMEN/ABSTRACT antes del cuerpo principal.",
                why="El resumen es obligatorio en tesis de grado y posgrado (150–350 palabras).",
                how_to_fix="Agregue RESUMEN con problema, objetivos, metodología y resultados principales.",
            )
        )
    elif abstract_words > profile.abstract_max_words:
        findings.append(
            Finding(
                module="Normativa",
                severity="warning",
                title="Resumen excede extensión recomendada",
                detail=(
                    f"Resumen detectado: ~{abstract_words} palabras "
                    f"(máx. recomendado {profile.abstract_max_words} para {profile.label})."
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
                    f"Resumen detectado: ~{abstract_words} palabras "
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
                detail=f"Resumen detectado: ~{abstract_words} palabras.",
            )
        )

    keywords_ok = bool(
        re.search(r"palabras?\s+clave|keywords", lower[:12000], re.IGNORECASE)
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
                title="Estilo de citación distinto al perfil institucional",
                detail=(
                    f"Perfil {profile.label} sugiere {profile.citation_style.upper()}; "
                    f"detectado: {style.upper()}."
                ),
                how_to_fix=f"Confirme con su director si debe usar {profile.citation_style.upper()}.",
            )
        )

    ref_count = len(parsed.get("bibliography") or {})
    checks["reference_count"] = ref_count
    if ref_count < profile.min_references:
        findings.append(
            Finding(
                module="Normativa",
                severity="warning",
                title="Bibliografía por debajo del mínimo del perfil",
                detail=(
                    f"{ref_count} referencias detectadas; mínimo sugerido para "
                    f"{profile.label}: {profile.min_references}."
                ),
                why="La profundidad bibliográfica es criterio explícito en rúbricas CONEAU y UNCUyo.",
                how_to_fix="Amplíe revisión de literatura con fuentes actuales y pertinentes al tema.",
            )
        )

    return findings, checks


def run_formal_audit(parsed: dict, config: AuditConfig) -> tuple[list[Finding], dict]:
    if not config.check_formal:
        return [], {}
    return audit_formal_requirements(parsed, config.profile)
