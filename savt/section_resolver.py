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
        "planteamiento",
        "encuadre del problema",
    ),
    "analisis_bibliometrico": (
        "análisis bibliométrico",
        "analisis bibliometrico",
        "estudio bibliométrico",
        "estudio bibliometrico",
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
        r"(?m)^(INTRODUCCI[ÓO]N|PLANTEAMIENTO(?:\s+DEL\s+(?:PROBLEMA|TEMA))?|PREGUNTA DE INVESTIGACI[ÓO]N|AN[ÁA]LISIS BIBLIOM[EÉ]TRICO|"
        r"MARCO TE[OÓ]RICO|MARCO CONCEPTUAL|FUNDAMENTACI[ÓO]N TE[OÓ]RICA|REVISI[ÓO]N(?:\s+DE\s+LITERATURA|\s+BIBLIOGR[AÁ]FICA)?|"
        r"METODOLOG[IÍ]A|MATERIALES Y M[EÉ]TODOS|MATERIAL Y M[EÉ]TODO|"
        r"RESULTADOS|HALLAZGOS(?:\s+PRINCIPALES)?|"
        r"DISCUSI[ÓO]N|INTERPRETACI[ÓO]N(?:\s+DE(?:\s+LOS)?\s+RESULTADOS)?|"
        r"CONCLUSIONES(?:\s+GENERALES|\s+FINALES)?|BIBLIOGRAF[IÍ]A|REFERENCIAS|ANEXOS?)\s*(?:$|\s+[A-ZÁÉÍÓÚÑ])",
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
    enriched, _meta = build_enriched_section_map(body, legacy_map=legacy_map)
    return enriched


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or "", re.UNICODE))


# Encabezados principales en línea (típico en PDF): «METODOLOGÍA El presente capítulo…»
_MAJOR_INLINE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (role, re.compile(pattern, re.IGNORECASE | re.MULTILINE))
    for role, pattern in [
        (
            "presentacion",
            r"(?:^|\n)\s*(?:Presentaci[oó]n(?:\s+del\s+Trabajo(?:\s+(?:de\s+)?Tesis| Final)?)?|"
            r"RESUMEN|ABSTRACT|S[ií]ntesis)\b",
        ),
        (
            "introduccion",
            r"(?:^|\n)\s*(?:INTRODUCCI[ÓO]N|PLANTEAMIENTO(?:\s+DEL\s+(?:PROBLEMA|TEMA))?)\b",
        ),
        (
            "marco_teorico",
            r"(?:^|\n)\s*(?:MARCO TE[OÓ]RICO|MARCO CONCEPTUAL|FUNDAMENTACI[ÓO]N TE[OÓ]RICA|"
            r"REVISI[ÓO]N(?:\s+DE\s+LITERATURA|\s+BIBLIOGR[AÁ]FICA)?|"
            r"ESTADO DEL ARTE|ANTECEDENTES)\b",
        ),
        (
            "metodologia",
            r"(?:^|\n)\s*(?:METODOLOG[IÍ]A|MATERIALES Y M[EÉ]TODOS|MATERIAL Y M[EÉ]TODO|"
            r"DISE[ÑN]O METODOL[ÓO]GICO|DECISIONES METODOL[ÓO]GICAS)\b",
        ),
        (
            "resultados",
            r"(?:^|\n)\s*(?:RESULTADOS(?:\s+Y\s+DISCUSI[ÓO]N)?|HALLAZGOS(?:\s+PRINCIPALES)?)\b",
        ),
        (
            "discusion",
            r"(?:^|\n)\s*(?:DISCUSI[ÓO]N|INTERPRETACI[ÓO]N(?:\s+DE(?:\s+LOS)?\s+RESULTADOS)?|"
            r"AN[ÁA]LISIS(?:\s+E?\s*)?INTERPRETACI[ÓO]N)\b",
        ),
        (
            "conclusiones",
            r"(?:^|\n)\s*CONCLUSIONES(?:\s+GENERALES|\s+FINALES)?\b",
        ),
    ]
)


def _scan_major_section_spans(body: str) -> list[tuple[int, str, str]]:
    """Primer encabezado principal de cada rol → (posición, rol, título detectado)."""
    hits: list[tuple[int, str, str]] = []

    marco_patterns = [
        (r"(?:^|\n)\s*MARCO TE[OÓ]RICO\b", "marco_teorico", "MARCO TEÓRICO"),
        (r"(?:^|\n)\s*MARCO CONCEPTUAL\b", "marco_teorico", "MARCO CONCEPTUAL"),
        (r"(?:^|\n)\s*FUNDAMENTACI[ÓO]N TE[OÓ]RICA\b", "marco_teorico", "FUNDAMENTACIÓN TEÓRICA"),
        (
            r"(?:^|\n)\s*REVISI[ÓO]N(?:\s+DE\s+LITERATURA|\s+BIBLIOGR[AÁ]FICA)\b",
            "marco_teorico",
            "REVISIÓN DE LITERATURA",
        ),
    ]
    for pattern, role, label in marco_patterns:
        match = re.search(pattern, body, re.IGNORECASE | re.MULTILINE)
        if match:
            hits.append((match.start(), role, label))
            break

    biblio_match = re.search(
        r"(?:^|\n)\s*AN[ÁA]LISIS BIBLIOM[EÉ]TRICO\b",
        body,
        re.IGNORECASE | re.MULTILINE,
    )
    if biblio_match:
        hits.append((biblio_match.start(), "analisis_bibliometrico", "ANÁLISIS BIBLIOMÉTRICO"))

    for role, pattern in _MAJOR_INLINE_PATTERNS:
        if role in {"marco_teorico", "analisis_bibliometrico"}:
            continue
        match = pattern.search(body)
        if not match:
            continue
        title = re.sub(r"\s+", " ", body[match.start() : match.end()].strip())[:140]
        hits.append((match.start(), role, title))
    hits.sort(key=lambda item: item[0])

    seen: set[str] = set()
    unique: list[tuple[int, str, str]] = []
    for pos, role, title in hits:
        if role in seen:
            continue
        seen.add(role)
        unique.append((pos, role, title))
    return unique


def _extract_objetivos_block(body: str) -> tuple[str, list[str]]:
    titles: list[str] = []
    start = None
    for pattern in (
        r"(?im)(?:^|\n)\s*\d+\.?\s*Objetivo general\b",
        r"(?im)(?:^|\n)\s*Objetivo general\b",
        r"(?im)(?:^|\n)\s*\d+\.?\s*Objetivos espec[ií]ficos\b",
        r"(?im)(?:^|\n)\s*Objetivos espec[ií]ficos\b",
    ):
        match = re.search(pattern, body)
        if match:
            start = match.start()
            titles.append(re.sub(r"\s+", " ", match.group(0).strip())[:120])
            break
    if start is None:
        return "", titles

    end_match = re.search(
        r"(?im)(?:^|\n)\s*MARCO TE[OÓ]RICO\b",
        body[start + 20 :],
    )
    end = start + 20 + end_match.start() if end_match else min(len(body), start + 12000)
    return body[start:end].strip(), titles


def _infer_introduccion_block(body: str, spans: list[tuple[int, str, str]]) -> tuple[str, list[str]]:
    if any(role == "introduccion" for _pos, role, _title in spans):
        return "", []

    marco_pos = min((pos for pos, role, _ in spans if role == "marco_teorico"), default=len(body))
    obj_match = re.search(r"(?im)(?:^|\n)\s*(?:\d+\.?\s*)?Objetivo general\b", body)
    obj_start = obj_match.start() if obj_match and obj_match.start() < marco_pos else marco_pos
    end_pos = min(marco_pos, obj_start)

    start_pos = 0
    for pattern in (
        r"(?im)(?:^|\n)\s*Tema de la tesis",
        r"(?im)(?:^|\n)\s*Pregunta de investigación",
        r"(?im)(?:^|\n)\s*Planteamiento",
        r"(?im)(?:^|\n)\s*1\.\s",
    ):
        match = re.search(pattern, body[: max(end_pos, 1)])
        if match:
            start_pos = match.start()
            break

    chunk = body[start_pos:end_pos].strip()
    if _word_count(chunk) < 150:
        chunk = body[:end_pos].strip()
    if _word_count(chunk) < 150:
        return "", []

    if re.search(r"(?im)\bINTRODUCCI[ÓO]N\b", chunk[:300]):
        titles = ["Introducción"]
    else:
        titles = ["Introducción (planteamiento, pregunta y justificación)"]
    return chunk, titles


def _map_from_spans(
    body: str,
    spans: list[tuple[int, str, str]],
) -> tuple[dict[str, str], dict[str, dict]]:
    sections: dict[str, str] = {}
    meta: dict[str, dict] = {}

    for idx, (pos, role, title) in enumerate(spans):
        next_pos = spans[idx + 1][0] if idx + 1 < len(spans) else len(body)
        chunk = body[pos:next_pos].strip()
        if _word_count(chunk) < 50:
            continue
        sections[role] = chunk
        meta[role] = {"detected_titles": [title]}

    return sections, meta


def build_enriched_section_map(
    body: str,
    legacy_map: dict[str, str] | None = None,
    *,
    conclusions_text: str | None = None,
) -> tuple[dict[str, str], dict[str, dict]]:
    """
    Mapa unificado de apartados: encabezados en línea (PDF), discover_headings,
    extract_section legacy y bloques inferidos (introducción, objetivos, conclusiones).
    """
    legacy = dict(legacy_map or {})
    for key, aliases in {
        "introduccion": ("introduc", "planteamiento"),
        "marco_teorico": ("marco teórico", "marco teorico", "marco conceptual"),
        "metodologia": ("metodolog", "materiales y métodos"),
        "resultados": ("resultado",),
        "discusion": ("discusi", "interpretación de resultados", "interpretacion de resultados"),
        "conclusiones": ("conclus",),
        "presentacion": ("presentacion", "presentación", "resumen", "abstract"),
    }.items():
        if key not in legacy:
            from savt.document_sections import extract_section

            text = extract_section(body, aliases)
            if text:
                legacy[key] = text

    canonical = build_canonical_map(body, min_chunk=150)
    spans = _scan_major_section_spans(body)
    inline_sections, inline_meta = _map_from_spans(body, spans)

    merged: dict[str, str] = dict(legacy)
    meta: dict[str, dict] = {}

    for source in (canonical, inline_sections, legacy):
        for role, text in source.items():
            if role not in merged or len(text) > len(merged.get(role, "")):
                merged[role] = text

    for role, info in inline_meta.items():
        meta[role] = {"detected_titles": list(info.get("detected_titles", []))}

    intro_text, intro_titles = _infer_introduccion_block(body, spans)
    obj_early = re.search(r"(?im)(?:^|\n)\s*(?:\d+\.?\s*)?Objetivo general\b", body)
    if obj_early and obj_early.start() > 80:
        pre_obj = body[: obj_early.start()].strip()
        if _word_count(pre_obj) >= 50:
            intro_text = pre_obj
            if re.search(r"(?im)Pregunta de investigación", pre_obj):
                intro_titles = ["Introducción (pregunta de investigación y planteamiento)"]
            elif re.search(r"(?im)\bINTRODUCCI[ÓO]N\b", pre_obj[:400]):
                intro_titles = ["Introducción"]
            else:
                intro_titles = ["Introducción (planteamiento y pregunta de investigación)"]

    if intro_text:
        merged["introduccion"] = intro_text
        meta["introduccion"] = {"detected_titles": intro_titles}

    obj_text, obj_titles = _extract_objetivos_block(body)
    if obj_text:
        merged["objetivos"] = obj_text
        meta["objetivos"] = {"detected_titles": obj_titles or ["Objetivos"]}

    if conclusions_text and len(conclusions_text) > len(merged.get("conclusiones", "")):
        merged["conclusiones"] = conclusions_text
        meta.setdefault("conclusiones", {"detected_titles": []})
        if "CONCLUSIONES" not in meta["conclusiones"]["detected_titles"]:
            meta["conclusiones"]["detected_titles"].append("CONCLUSIONES")

    for role, text in merged.items():
        if role not in meta:
            meta[role] = {"detected_titles": ["Detectado por contenido"]}
        elif not meta[role].get("detected_titles"):
            meta[role]["detected_titles"] = ["Detectado por contenido"]

    return merged, meta


def _first_match_start(body: str, pattern: str, *, ignore_case: bool = True) -> int | None:
    flags = re.MULTILINE | (re.IGNORECASE if ignore_case else 0)
    match = re.search(pattern, body, flags)
    return match.start() if match else None


def _first_match_in_order(body: str, patterns: list[str], *, ignore_case: bool = True) -> int | None:
    """Devuelve la primera coincidencia según prioridad de patrones (no la más temprana en el texto)."""
    for pattern in patterns:
        pos = _first_match_start(body, pattern, ignore_case=ignore_case)
        if pos is not None:
            return pos
    return None


def _first_match_start_any(body: str, patterns: list[str], *, ignore_case: bool = True) -> int | None:
    best: int | None = None
    for pattern in patterns:
        pos = _first_match_start(body, pattern, ignore_case=ignore_case)
        if pos is not None and (best is None or pos < best):
            best = pos
    return best


# Encabezado de sección: inicio de línea y título seguido de salto, fin o numeración.
_PARTE = r"(?:^|\n)\s*(?:PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA)\s+PARTE\s*[-–—]?\s*"
_MARCO_HEADING = (
    r"(?im)(?:^|\n)\s*MARCO TE[OÓ]RICO(?:\s*[-–—]?\s*CONCEPTUAL)?\b"
)


def _strip_leading_toc(body: str) -> str:
    """
    Omite índice o tabla de contenidos duplicada al inicio del PDF.
    Típico cuando los encabezados aparecen dos veces: primero como índice y luego como cuerpo.
    """
    if not body.strip():
        return body

    intro_hits = [m.start() for m in re.finditer(r"(?im)(?:^|\n)\s*INTRODUCCI[ÓO]N\b", body)]
    metod_hits = [
        m.start()
        for m in re.finditer(r"(?im)(?:^|\n)\s*METODOLOG[IÍ]A\s", body)
    ]

    if len(intro_hits) >= 2 and metod_hits:
        toc_words = _word_count(body[intro_hits[0] : metod_hits[0]])
        if toc_words < 800:
            if len(metod_hits) >= 2 and metod_hits[0] < len(body) * 0.05:
                real_metod = metod_hits[-1]
                intros_before = [pos for pos in intro_hits if pos < real_metod]
                if intros_before:
                    return body[intros_before[-1] :].lstrip()
            return body[intro_hits[1] :].lstrip()

    if len(metod_hits) >= 2 and metod_hits[0] < len(body) * 0.05:
        if _word_count(body[: metod_hits[0]]) < 800:
            intros_before = [pos for pos in intro_hits if pos < metod_hits[-1]]
            if intros_before:
                return body[intros_before[-1] :].lstrip()

    return body


def _all_pattern_starts(body: str, patterns: list[str], *, ignore_case: bool = True) -> list[int]:
    flags = re.MULTILINE | (re.IGNORECASE if ignore_case else 0)
    starts: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, body, flags):
            starts.append(match.start())
    return sorted(set(starts))


def _pick_substantive_heading(
    body: str,
    patterns: list[str],
    *,
    ignore_case: bool = True,
    min_segment_words: int = 350,
) -> int | None:
    """Elige el encabezado cuya sección siguiente tiene más contenido (evita entradas de índice)."""
    starts = _all_pattern_starts(body, patterns, ignore_case=ignore_case)
    if not starts:
        return None
    if len(starts) == 1:
        return starts[0]

    best_pos = starts[0]
    best_words = 0
    for idx, pos in enumerate(starts):
        next_pos = starts[idx + 1] if idx + 1 < len(starts) else min(len(body), pos + 25000)
        segment_words = _word_count(body[pos:next_pos])
        if segment_words > best_words:
            best_words = segment_words
            best_pos = pos

    if best_words >= min_segment_words:
        return best_pos
    return _first_match_in_order(body, patterns, ignore_case=ignore_case)


def _find_objetivos_start(body: str) -> tuple[int | None, str]:
    patterns_titles = [
        (
            r"(?im)(?:^|\n)\s*Objetivos y pregunta de investigaci",
            "Objetivos y pregunta de investigación",
        ),
        (
            r"(?im)(?:^|\n)\s*PREGUNTA DE INVESTIGACI[ÓO]N,\s*OBJETIVOS E HIP[ÓO]TESIS",
            "Pregunta de investigación, objetivos e hipótesis",
        ),
        (
            r"(?im)(?:^|\n)\s*\d+\.?\s*Pregunta de investigaci",
            "Pregunta de investigación",
        ),
        (
            r"(?im)(?:^|\n)\s*\d+\.?\s*Objetivo general",
            "Objetivos",
        ),
        (
            r"(?im)(?:^|\n)\s*Objetivo general\b",
            "Objetivos",
        ),
        (
            r"(?im)(?:^|\n)\s*Objetivos espec[ií]ficos\b",
            "Objetivos específicos",
        ),
    ]
    for pattern, title in patterns_titles:
        pos = _first_match_start(body, pattern)
        if pos is not None:
            return pos, title
    return None, ""


def _find_major_section_boundaries(
    body: str,
    *,
    pos_objetivos: int | None = None,
) -> list[tuple[int, str, str]]:
    """Localiza encabezados principales; prioriza estructura por PARTES y evita falsos positivos."""
    role_patterns: list[tuple[str, str, list[str], bool]] = [
        (
            "analisis_bibliometrico",
            "Análisis bibliométrico",
            [
                rf"(?im){_PARTE}AN[ÁA]LISIS BIBLIOM[EÉ]TRICO",
                r"(?m)(?:^|\n)\s*AN[ÁA]LISIS BIBLIOM[EÉ]TRICO\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*AN[ÁA]LISIS BIBLIOM[EÉ]TRICO\b(?=\s+[A-ZÁÉÍÓÚÑ])",
            ],
            False,
        ),
        (
            "marco_teorico",
            "Marco teórico",
            [
                rf"(?im){_PARTE}ENCUADRE TE[OÓ]RICO",
                _MARCO_HEADING + r"(?=\s|\n|$)",
                r"(?m)(?:^|\n)\s*ENCUADRE TE[OÓ]RICO\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*MARCO TE[OÓ]RICO\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*MARCO CONCEPTUAL\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*ESTADO DEL ARTE\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*REVISI[ÓO]N(?:\s+DE\s+LITERATURA|\s+BIBLIOGR[AÁ]FICA)\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*MARCO TE[OÓ]RICO\b(?=\s+[A-ZÁÉÍÓÚÑ])",
            ],
            True,
        ),
        (
            "metodologia",
            "Metodología",
            [
                rf"(?im){_PARTE}DECISIONES EMP",
                rf"(?im){_PARTE}METODOL",
                r"(?im)(?:^|\n)\s*METODOLOG[IÍ]A\s",
                r"(?im)(?:^|\n)\s*METODOLOG[IÍ]A\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*MATERIALES Y M[EÉ]TODOS\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*DISE[ÑN]O METODOL[ÓO]GICO\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*METODOLOG[IÍ]A\b(?=\s+[A-ZÁÉÍÓÚÑ])",
            ],
            True,
        ),
        (
            "resultados",
            "Resultados",
            [
                rf"(?im){_PARTE}AN[ÁA]LISIS Y RESULTADOS",
                rf"(?im){_PARTE}RESULTADOS",
                r"(?m)(?:^|\n)\s*Resultados\s",
                r"(?m)(?:^|\n)\s*RESULTADOS(?:\s+Y\s+DISCUSI[ÓO]N)?\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*AN[ÁA]LISIS(?:\s+DE\s+)?RESULTADOS\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*RESULTADOS\b(?=\s+[A-ZÁÉÍÓÚÑ])",
            ],
            False,
        ),
        (
            "discusion",
            "Discusión",
            [
                rf"(?im){_PARTE}DISCUSI[ÓO]N",
                r"(?m)(?:^|\n)\s*DISCUSI[ÓO]N\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*INTERPRETACI[ÓO]N(?:\s+DE(?:\s+LOS)?\s+RESULTADOS)?\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*DISCUSI[ÓO]N\b(?=\s+[A-ZÁÉÍÓÚÑ])",
            ],
            False,
        ),
        (
            "conclusiones",
            "Conclusiones",
            [
                rf"(?im){_PARTE}CONCLUSIONES",
                r"(?m)(?:^|\n)\s*CONCLUSIONES(?:\s+GENERALES|\s+FINALES)?\s*(?:\n|$|\d+\.)",
                r"(?m)(?:^|\n)\s*CONCLUSIONES\b(?=\s+[A-ZÁÉÍÓÚÑ])",
            ],
            True,
        ),
    ]

    boundaries: list[tuple[int, str, str]] = []
    for role, default_title, patterns, ignore_case in role_patterns:
        if role == "marco_teorico" and pos_objetivos is not None:
            starts = [
                p for p in _all_pattern_starts(body, patterns, ignore_case=ignore_case) if p >= pos_objetivos
            ]
            if starts:
                best_pos = starts[0]
                best_words = 0
                for idx, pos_candidate in enumerate(starts):
                    next_pos = starts[idx + 1] if idx + 1 < len(starts) else len(body)
                    segment_words = _word_count(body[pos_candidate:next_pos])
                    if segment_words > best_words:
                        best_words = segment_words
                        best_pos = pos_candidate
                pos = best_pos if best_words >= 350 else starts[0]
            else:
                pos = _pick_substantive_heading(body, patterns, ignore_case=ignore_case)
        elif role == "resultados":
            pos = _first_match_in_order(body, patterns, ignore_case=ignore_case)
        else:
            pos = _pick_substantive_heading(body, patterns, ignore_case=ignore_case)
        if pos is not None:
            boundaries.append((pos, role, default_title))

    boundaries.sort(key=lambda item: item[0])
    seen_roles: set[str] = set()
    unique: list[tuple[int, str, str]] = []
    for pos, role, title in boundaries:
        if role in seen_roles:
            continue
        seen_roles.add(role)
        unique.append((pos, role, title))
    return unique


def build_non_overlapping_word_partition(body: str) -> tuple[dict[str, str], dict[str, dict]]:
    """
    Parte el cuerpo en tramos mutuamente excluyentes (sin doble conteo).
    Cada carácter del body pertenece como máximo a un rol canónico.
    """
    if not body.strip():
        return {}, {}

    body = _strip_leading_toc(body)

    pos_obj_start, obj_title = _find_objetivos_start(body)
    major = _find_major_section_boundaries(body, pos_objetivos=pos_obj_start)

    first_major = major[0][0] if major else len(body)
    obj_end = first_major
    for pos, role, _title in major:
        if role == "analisis_bibliometrico" and pos <= first_major:
            obj_end = pos
            break

    sections: dict[str, str] = {}
    meta: dict[str, dict] = {}

    if pos_obj_start is not None and pos_obj_start < first_major:
        intro = body[:pos_obj_start].strip()
        if intro:
            sections["introduccion"] = intro
            meta["introduccion"] = {"detected_titles": ["Introducción"]}
        obj_block = body[pos_obj_start:obj_end].strip()
        if obj_block:
            sections["objetivos"] = obj_block
            meta["objetivos"] = {"detected_titles": [obj_title or "Pregunta, objetivos e hipótesis"]}
    else:
        intro = body[:first_major].strip()
        if intro:
            sections["introduccion"] = intro
            if re.search(r"(?im)\bINTRODUCCI[ÓO]N\b", intro[:300]):
                meta["introduccion"] = {"detected_titles": ["Introducción"]}
            else:
                meta["introduccion"] = {
                    "detected_titles": ["Introducción (planteamiento y pregunta de investigación)"]
                }

    for idx, (pos, role, title) in enumerate(major):
        next_pos = major[idx + 1][0] if idx + 1 < len(major) else len(body)
        chunk = body[pos:next_pos].strip()
        if _word_count(chunk) < 20:
            continue
        sections[role] = chunk
        # Título detectado: texto del encabezado en el documento (hasta ~120 caracteres).
        heading = re.sub(r"\s+", " ", body[pos : pos + 160].split("\n")[0].strip())[:120]
        meta[role] = {"detected_titles": [heading or title]}

    return sections, meta
