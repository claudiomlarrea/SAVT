"""Mapeo flexible de encabezados reales → roles canónicos de una tesis/trabajo final."""

from __future__ import annotations

import re
from dataclasses import dataclass

from savt.bibliography_styles import strip_accents

# Roles canónicos evaluables (independientes del nombre que use cada universidad).
CANONICAL_ROLES: dict[str, tuple[str, ...]] = {
    "presentacion": (
        "presentacion",
        "presentación",
        "resumen",
        "abstract",
        "síntesis",
        "sintesis",
        "sinopsis",
    ),
    "introduccion": (
        "introduccion",
        "introducción",
        "planteamiento del tema",
        "planteamiento general",
        "planteamiento del problema",
        "problematica",
        "problemática",
    ),
    "marco_teorico": (
        "marco teórico",
        "marco teorico",
        "marco conceptual",
        "marco referencial",
        "fundamentación teórica",
        "fundamentacion teorica",
        "fundamentacion teorica",
        "revisión de literatura",
        "revision de literatura",
        "revision bibliografica",
        "revisión bibliográfica",
        "estado del arte",
        "antecedentes",
        "encuadre teórico",
        "encuadre teorico",
        "marco de referencia",
        "análisis bibliométrico",
        "analisis bibliometrico",
        "bases teóricas",
        "bases teoricas",
    ),
    "metodologia": (
        "metodología",
        "metodologia",
        "materiales y métodos",
        "materiales y metodos",
        "material y método",
        "material y metodo",
        "diseño metodológico",
        "diseno metodologico",
        "decisiones empíricas",
        "decisiones empiricas",
        "decisiones metodológicas",
        "decisiones metodologicas",
        "procedimiento",
        "diseño del estudio",
        "diseno del estudio",
        "enfoque metodológico",
        "enfoque metodologico",
    ),
    "resultados": (
        "resultados",
        "resultado",
        "hallazgos",
        "análisis y resultados",
        "analisis y resultados",
        "análisis de resultados",
        "analisis de resultados",
        "análisis de datos",
        "analisis de datos",
    ),
    "discusion": (
        "discusión",
        "discusion",
        "discussión",
        "interpretación de los resultados",
        "interpretacion de los resultados",
        "interpretación de resultados",
        "interpretacion de resultados",
        "análisis e interpretación",
        "analisis e interpretacion",
    ),
    "conclusiones": (
        "conclusiones",
        "conclusión",
        "conclusion",
        "conclusiones generales",
        "conclusiones y recomendaciones",
        "conclusiones finales",
    ),
    "objetivos": (
        "objetivos específicos",
        "objetivos especificos",
        "objetivo general",
        "objetivos del trabajo",
        "objetivos de la investigación",
        "objetivos de la investigacion",
    ),
}

# Encabezados de parte/volumen que orientan el rol cuando no hay título explícito.
PART_ROLE_HINTS: dict[str, str] = {
    "encuadre": "marco_teorico",
    "teorico": "marco_teorico",
    "teórico": "marco_teorico",
    "metodolog": "metodologia",
    "empiric": "metodologia",
    "resultado": "resultados",
    "analisis": "resultados",
    "análisis": "resultados",
    "conclus": "conclusiones",
}


@dataclass
class Heading:
    start: int
    end: int
    title: str
    role: str | None = None


def _normalize_heading(text: str) -> str:
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", text.strip())
    text = re.sub(r"^(?:CAPÍTULO|CAPITULO|PARTE|TOMO)\s+[IVXLC\d]+\.?\s*", "", text, flags=re.I)
    return strip_accents(text.lower()).strip()


def classify_heading(title: str, part_context: str = "") -> str | None:
    """Asigna un rol canónico a un encabezado, o None si no es sección evaluable."""
    norm = _normalize_heading(title)
    if not norm or len(norm) < 4:
        return None

    # Evitar falsos positivos del índice (líneas muy cortas con número de página).
    if re.search(r"\.{3,}\s*\d+\s*$", title):
        return None

    best_role: str | None = None
    best_len = 0
    for role, aliases in CANONICAL_ROLES.items():
        for alias in aliases:
            alias_n = strip_accents(alias.lower())
            if alias_n in norm and len(alias_n) > best_len:
                best_role = role
                best_len = len(alias_n)

    if best_role:
        return best_role

    combined = f"{part_context} {norm}".lower()
    for hint, role in PART_ROLE_HINTS.items():
        if hint in combined:
            return role
    return None


def discover_headings(body: str) -> list[Heading]:
    """Localiza encabezados típicos de tesis (capítulos, partes, numeración multinivel)."""
    if not body:
        return []

    patterns = [
        r"(?m)^(CAPÍTULO|CAPITULO)\s+([IVXLC\d]+)\.?\s*(.+)$",
        r"(?m)^(PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA)\s+PARTE(?:\s+[-–]?\s*(.+))?$",
        r"(?m)^(TOMO\s+[IVXLC\d]+)\s*$",
        r"(?m)^(INTRODUCCI[ÓO]N|PREGUNTA DE INVESTIGACI[ÓO]N|AN[ÁA]LISIS BIBLIOM[EÉ]TRICO|"
        r"MARCO TE[OÓ]RICO|MARCO CONCEPTUAL|METODOLOG[IÍ]A|MATERIALES Y M[EÉ]TODOS|"
        r"RESULTADOS|DISCUSI[ÓO]N|CONCLUSIONES|BIBLIOGRAF[IÍ]A|REFERENCIAS|ANEXOS?)\s*$",
        r"(?m)^(\d+(?:\.\d+)*\.?\s+[A-ZÁÉÍÓÚÑ][^\n]{4,120})$",
        r"(?m)^(Presentaci[oó]n(?:\s+del\s+Trabajo(?:\s+(?:de\s+)?Tesis| Final)?)?)\s*$",
        r"(?m)^(RESUMEN|ABSTRACT|S[ií]ntesis)\s*$",
    ]

    found: list[tuple[int, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, body, re.IGNORECASE):
            if match.lastindex and match.lastindex >= 3:
                title = match.group(3).strip() if match.group(3) else match.group(0).strip()
            elif match.lastindex and match.lastindex >= 2 and "PARTE" in pattern:
                subtitle = (match.group(2) or "").strip()
                title = f"{match.group(1)} PARTE {subtitle}".strip()
            else:
                title = match.group(0).strip()
            found.append((match.start(), title))

    found.sort(key=lambda x: x[0])
    # Deduplicar posiciones cercanas (mismo encabezado capturado por varios patrones).
    merged: list[tuple[int, str]] = []
    for pos, title in found:
        if merged and pos - merged[-1][0] < 3:
            if len(title) > len(merged[-1][1]):
                merged[-1] = (pos, title)
            continue
        merged.append((pos, title))

    part_context = ""
    headings: list[Heading] = []
    for idx, (pos, title) in enumerate(merged):
        if re.search(r"\bPARTE\b", title, re.I):
            part_context = title
        end = merged[idx + 1][0] if idx + 1 < len(merged) else len(body)
        role = classify_heading(title, part_context)
        headings.append(Heading(start=pos, end=end, title=title, role=role))
    return headings


def build_canonical_map(body: str, min_chunk: int = 200) -> dict[str, str]:
    """
    Agrega el contenido bajo cada rol canónico.
    Varias secciones del mismo rol (p. ej. varias «Interpretación de resultados») se concatenan.
    """
    headings = discover_headings(body)
    buckets: dict[str, list[str]] = {}

    for heading in headings:
        if not heading.role:
            continue
        start = heading.start + len(heading.title)
        chunk = body[start:heading.end].strip()
        if len(chunk) < min_chunk:
            continue
        buckets.setdefault(heading.role, []).append(chunk)

    return {role: "\n\n".join(parts) for role, parts in buckets.items() if parts}


def get_canonical_section(body: str, role: str, fallback_map: dict[str, str] | None = None) -> str:
    """Texto de un rol canónico; usa mapa precalculado o lo reconstruye."""
    if fallback_map and fallback_map.get(role):
        return fallback_map[role]
    return build_canonical_map(body).get(role, "")


def merged_section_map(body: str, legacy_map: dict[str, str] | None = None) -> dict[str, str]:
    """Combina detección legacy (extract_section) con el mapa canónico."""
    canonical = build_canonical_map(body)
    legacy = legacy_map or {}
    merged = dict(legacy)
    for role, text in canonical.items():
        if role not in merged or len(text) > len(merged.get(role, "")):
            merged[role] = text
    return merged
