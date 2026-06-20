from __future__ import annotations

import re

from savt.bibliography_styles import strip_accents

SECTION_END_MARKERS = (
    r"CAPÍTULO|CAPITULO|"
    r"INTRODUCCI[ÓO]N|PREGUNTA DE INVESTIGACI[ÓO]N|"
    r"AN[ÁA]LISIS BIBLIOM[EÉ]TRICO|MARCO TE[OÓ]RICO|MARCO CONCEPTUAL|"
    r"METODOLOG[IÍ]A|MATERIALES Y M[EÉ]TODOS|RESULTADOS|DISCUSI[ÓO]N|"
    r"CONCLUSIONES|BIBLIOGRAF[IÍ]A|REFERENCIAS|ANEXOS"
)

ABSTRACT_PATTERNS = [
    (
        "resumen",
        r"(?is)(?:^|\n)\s*RESUMEN\s*\n(.+?)(?=\n\s*(?:PALABRAS?\s+CLAVE|KEYWORDS|ABSTRACT|ÍNDICE|INDICE|INTRODUCCI[ÓO]N|CAPÍTULO|CAPITULO|\d+\.\s+[A-Z]))",
    ),
    (
        "abstract",
        r"(?is)(?:^|\n)\s*ABSTRACT\s*\n(.+?)(?=\n\s*(?:KEYWORDS|PALABRAS?\s+CLAVE|ÍNDICE|INDICE|INTRODUCCI[ÓO]N|CAPÍTULO|CAPITULO|\d+\.\s+[A-Z]))",
    ),
    (
        "presentacion",
        r"(?is)(?:^|\n)\s*Presentaci[oó]n del Trabajo(?: de Tesis| Final)?\s*(?:\n|\s+)(.+?)"
        r"(?=\n\s*(?:INTRODUCCI[ÓO]N|PREGUNTA DE INVESTIGACI[ÓO]N|CAPÍTULO|CAPITULO|\d+\.\s+[A-Z]))",
    ),
    (
        "sintesis",
        r"(?is)(?:^|\n)\s*S[ií]ntesis\s*\n(.+?)(?=\n\s*(?:PALABRAS?\s+CLAVE|ÍNDICE|INDICE|INTRODUCCI[ÓO]N|CAPÍTULO|CAPITULO))",
    ),
]

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "introduccion": ("introduc", "planteamiento general", "planteamiento del tema"),
    "marco_teorico": (
        "marco teórico",
        "marco teorico",
        "marco conceptual",
        "fundamentación teórica",
        "fundamentacion teorica",
        "revisión de literatura",
        "revision de literatura",
        "estado del arte",
        "antecedentes",
        "marco referencial",
        "análisis bibliométrico",
        "analisis bibliometrico",
    ),
    "metodologia": (
        "metodolog",
        "materiales y métodos",
        "material y metodo",
        "diseño metodológico",
        "diseno metodologico",
    ),
    "resultados": ("resultado", "hallazgo"),
    "discusion": ("discusi", "análisis de resultados", "analisis de resultados", "interpretación de resultados"),
    "conclusiones": ("conclus",),
}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, re.UNICODE))


def extract_title(full_text: str, filename: str = "") -> str:
    head = (full_text or "")[:12000]
    patterns = [
        r"(?is)(?:TRABAJO FINAL(?: DE TESIS)?|TESIS(?: DOCTORAL)?|TFM|TFG)\s*\n+(.+?)(?:\n\n|\nMaestr|\nDirector|\nDoctor|\nAlumn|\nEstudiant)",
        r"(?is)(?:TÍTULO|TITULO)\s*:?\s*(.+?)(?:\n\n|\nMaestr|\nDirector)",
        r"(?is)^([A-ZÁÉÍÓÚÑ][^\n]{20,180}(?:\n[^\n]{10,120}){0,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, head)
        if match:
            title = re.sub(r"\s+", " ", match.group(1)).strip()
            if len(title) > 25 and "UNIVERSIDAD" not in title.upper()[:20]:
                return title

    stem = re.sub(r"[_\-0-9]+", " ", filename)
    stem = re.sub(r"\.(docx|pdf)$", "", stem, flags=re.I).strip()
    if len(stem) > 8:
        return stem
    return ""


def infer_topic_keywords(full_text: str, body: str, filename: str = "") -> list[str]:
    title = extract_title(full_text, filename)
    sources = [title, filename]
    if body:
        head_body = body[:8000]
        q_match = re.search(r"¿[^?]{20,200}\?", head_body)
        if q_match:
            sources.append(q_match.group(0))

    stop = {
        "trabajo",
        "final",
        "tesis",
        "maestria",
        "maestría",
        "doctorado",
        "universidad",
        "presentacion",
        "presentación",
        "analisis",
        "análisis",
        "estudio",
        "investigacion",
        "investigación",
        "argentina",
        "postpandemia",
        "inteligencia",
        "artificial",
        "datos",
        "abiertos",
        "empirico",
        "empírico",
        "principal",
        "estos",
        "componentes",
        "constituyen",
        "directriz",
        "delimitan",
        "problema",
        "abordar",
        "definen",
        "metas",
        "alcanzar",
        "objetivos",
        "metodologia",
        "metodología",
        "capitulo",
        "capítulo",
        "introduccion",
        "introducción",
        "documento",
        "informe",
        "claudio",
        "larrea",
    }

    words: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not source:
            continue
        for word in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñ]{5,}", strip_accents(source.lower())):
            if word in stop or word in seen:
                continue
            seen.add(word)
            words.append(word)
    return words[:15]


def assess_cover(full_text: str) -> dict[str, bool]:
    head = (full_text or "")[:8000].lower()
    return {
        "institucion": bool(
            re.search(r"\b(universidad|facultad|instituto|college|university|school of)\b", head)
        ),
        "titulo": len(extract_title(full_text)) > 20,
        "director": bool(
            re.search(
                r"\b(director(?:a)?(?:\s+del\s+trabajo)?|tutor(?:a)?|asesor(?:a)?|"
                r"codirector(?:a)?|mentor(?:a)?)\b",
                head,
            )
        ),
        "autor": bool(
            re.search(
                r"\b(maestrando(?:a)?|doctorando(?:a)?|alumn[oa]|estudiante|tesista|"
                r"autor(?:a)?(?:\s+del\s+trabajo)?|candidat[oa])\b",
                head,
            )
        ),
    }


def extract_abstract(full_text: str) -> tuple[str, int, str]:
    for label, pattern in ABSTRACT_PATTERNS:
        match = re.search(pattern, full_text or "")
        if match:
            text = re.sub(r"\s+", " ", match.group(1)).strip()
            if _word_count(text) >= 80:
                return text, _word_count(text), label
    return "", 0, ""


def _heading_positions(body: str) -> list[tuple[int, str, str]]:
    positions: list[tuple[int, str, str]] = []
    patterns = [
        (r"(?m)^(CAPÍTULO|CAPITULO)\s+[IVXLC\d]+[\.\s]+(.+)$", "capitulo"),
        (r"(?m)^(INTRODUCCI[ÓO]N|PREGUNTA DE INVESTIGACI[ÓO]N|AN[ÁA]LISIS BIBLIOM[EÉ]TRICO|"
         r"MARCO TE[OÓ]RICO|MARCO CONCEPTUAL|METODOLOG[IÍ]A|MATERIALES Y M[EÉ]TODOS|"
         r"RESULTADOS|DISCUSI[ÓO]N|CONCLUSIONES)\s*$", "mayus"),
        (r"(?m)^(\d+\.\s+[A-ZÁÉÍÓÚÑ][^\n]{5,80})$", "numerada"),
    ]
    for pattern, kind in patterns:
        for match in re.finditer(pattern, body, re.IGNORECASE):
            heading = match.group(0).strip()
            positions.append((match.start(), kind, heading))
    positions.sort(key=lambda x: x[0])
    return positions


def extract_section(body: str, aliases: tuple[str, ...]) -> str:
    if not body:
        return ""
    lower_aliases = [a.lower() for a in aliases]
    positions = _heading_positions(body)

    for idx, (pos, _kind, heading) in enumerate(positions):
        heading_l = heading.lower()
        if not any(alias in heading_l for alias in lower_aliases):
            continue
        start = pos + len(heading)
        end = len(body)
        if idx + 1 < len(positions):
            end = positions[idx + 1][0]
        chunk = body[start:end].strip()
        if len(chunk) > 200:
            return chunk

    for alias in lower_aliases:
        pattern = rf"(?is)\b{re.escape(alias)}\b(.+?)(?=\n(?:{SECTION_END_MARKERS})\b|\Z)"
        match = re.search(pattern, body)
        if match and len(match.group(0)) > 300:
            return match.group(0).strip()
    return ""


def get_section_map(body: str) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for key, aliases in SECTION_ALIASES.items():
        text = extract_section(body, aliases)
        if text:
            mapped[key] = text
    return mapped


def suggest_degree_profile(full_text: str, page_estimate: float) -> str:
    head = (full_text or "")[:6000].lower()
    if re.search(r"\bdoctorado\b|\btesis doctoral\b|\bph\.?d\b", head):
        return "doctorado"
    if re.search(r"\bespecializaci[oó]n\b", head):
        return "especializacion"
    if re.search(r"\bmaestr[ií]a profesional\b|\bmaster professional\b", head):
        return "maestria_profesional"
    if re.search(r"\bmaestr[ií]a\b|\bmaster\b|\bmag[ií]ster\b", head):
        return "maestria_academica"
    if re.search(r"\btesina\b|\btrabajo final de grado\b|\blicenciatura\b|\btfg\b|\btfi\b", head):
        return "grado_tesina"
    if page_estimate >= 80:
        return "maestria_academica"
    if page_estimate >= 50:
        return "grado_tesina"
    return "grado_tesina"
