"""Confirmación editable de apartados detectados antes de auditar."""

from __future__ import annotations

import re
import unicodedata

from savt.word_stats import CANONICAL_SECTION_ORDER, count_words

ROLE_LABELS: dict[str, str] = {role: label for role, label in CANONICAL_SECTION_ORDER}
ROLE_LABELS["bibliografia"] = "Bibliografía / referencias"
ROLE_LABELS["otros"] = "Otro / sin clasificar"
ROLE_LABELS["omitir"] = "No existe / omitir"

EDITABLE_ROLES: tuple[str, ...] = tuple(role for role, _ in CANONICAL_SECTION_ORDER) + (
    "bibliografia",
    "otros",
    "omitir",
)

CONFIDENCE_LABELS = {
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
}


def confidence_for_section(
    *,
    role: str,
    words: int,
    detected_as: str = "",
    source: str = "",
    structure_source: str = "",
) -> tuple[str, str]:
    """Devuelve (nivel, etiqueta) de confianza para un apartado detectado."""
    title = (detected_as or "").strip().lower()
    weak_titles = {
        "",
        "—",
        "detectado por contenido",
    }
    weak_title = title in weak_titles or "detectado por contenido" in title

    if source == "manual" or structure_source == "manual":
        if words >= 80 and not weak_title:
            return "high", CONFIDENCE_LABELS["high"]
        if words >= 40:
            return "medium", CONFIDENCE_LABELS["medium"]
        return "low", CONFIDENCE_LABELS["low"]

    if source == "index" or structure_source in {"index", "capitulos"}:
        if words >= 200 and not weak_title:
            return "high", CONFIDENCE_LABELS["high"]
        if words >= 80:
            return "medium", CONFIDENCE_LABELS["medium"]
        return "low", CONFIDENCE_LABELS["low"]

    if words >= 400 and not weak_title:
        return "high", CONFIDENCE_LABELS["high"]
    if words >= 150:
        return "medium", CONFIDENCE_LABELS["medium"]
    if words >= 80:
        return "medium" if not weak_title else "low", (
            CONFIDENCE_LABELS["medium"] if not weak_title else CONFIDENCE_LABELS["low"]
        )
    return "low", CONFIDENCE_LABELS["low"]


def enrich_detected_sections(
    sections: list[dict],
    *,
    structure_source: str = "",
) -> list[dict]:
    """Añade confianza y campos de edición a la lista de apartados detectados."""
    enriched: list[dict] = []
    for item in sections:
        role = item.get("role") or "otros"
        words = int(item.get("words") or 0)
        level, label = confidence_for_section(
            role=role,
            words=words,
            detected_as=str(item.get("detected_as") or ""),
            source=str(item.get("source") or ""),
            structure_source=structure_source,
        )
        enriched.append(
            {
                **item,
                "role": role,
                "confidence": level,
                "confidence_label": label,
                "confirmed_role": role,
                "include": True,
            }
        )
    return enriched


def role_options() -> list[str]:
    return [ROLE_LABELS[role] for role in EDITABLE_ROLES]


def label_to_role(label: str) -> str:
    for role, name in ROLE_LABELS.items():
        if name == label:
            return role
    return "otros"


def editor_rows(sections: list[dict]) -> list[dict]:
    """Filas listas para st.data_editor."""
    rows: list[dict] = []
    for idx, item in enumerate(sections, start=1):
        role = item.get("confirmed_role") or item.get("role") or "otros"
        rows.append(
            {
                "N°": idx,
                "Incluir": bool(item.get("include", True)),
                "Detectado como": item.get("detected_as") or "—",
                "Apartado canónico": ROLE_LABELS.get(role, ROLE_LABELS["otros"]),
                "Confianza": item.get("confidence_label") or "—",
                "Palabras": int(item.get("words") or 0),
                "% del cuerpo": item.get("percent_label") or "—",
                "_role_original": item.get("role") or "otros",
                "_text_key": item.get("role") or f"otros_{idx}",
            }
        )
    return rows


def overrides_from_editor(rows: list[dict]) -> list[dict]:
    """Normaliza filas editadas a overrides {role_original, confirmed_role, include}."""
    overrides: list[dict] = []
    for row in rows:
        original = str(row.get("_role_original") or "otros")
        confirmed = label_to_role(str(row.get("Apartado canónico") or ROLE_LABELS["otros"]))
        overrides.append(
            {
                "role_original": original,
                "confirmed_role": confirmed,
                "include": bool(row.get("Incluir", True)),
                "detected_as": str(row.get("Detectado como") or ""),
                "words": int(row.get("Palabras") or 0),
            }
        )
    return overrides


def apply_section_overrides(parsed: dict, overrides: list[dict]) -> dict:
    """
    Reescribe section_map / section_meta / index_sections según confirmación del usuario.
    No regenera texto: reasigna roles canónicos sobre los bloques ya detectados.
    """
    if not overrides:
        return parsed

    section_map = dict(parsed.get("section_map") or {})
    section_meta = dict(parsed.get("section_meta") or {})
    role_texts, meta = {}, {}

    # Preferir el mapa canónico existente; si hay index_sections, usar sus textos.
    if parsed.get("structure_source") == "index" and parsed.get("index_sections"):
        for item in parsed["index_sections"]:
            role = item.get("role") or "otros"
            text = (parsed.get("section_map") or {}).get(role) or item.get("text") or ""
            if not text and role in section_map:
                text = section_map[role]
            role_texts.setdefault(role, "")
            if text and len(text) > len(role_texts[role]):
                role_texts[role] = text
            titles = [item.get("title") or role]
            meta.setdefault(role, {"detected_titles": titles})
    else:
        role_texts = dict(section_map)
        meta = dict(section_meta)

    # Fallback: textos del partition si el mapa está vacío.
    if not role_texts:
        from savt.word_stats import get_section_word_partition

        role_texts, meta = get_section_word_partition(parsed)

    new_map: dict[str, str] = {}
    new_meta: dict[str, dict] = {}
    remapped_index: list[dict] = []

    for override in overrides:
        if not override.get("include", True):
            continue
        confirmed = override.get("confirmed_role") or "otros"
        if confirmed in {"omitir", "otros"}:
            continue
        original = override.get("role_original") or confirmed
        text = role_texts.get(original) or role_texts.get(confirmed) or ""
        if not text and original in section_map:
            text = section_map[original]
        if not text.strip():
            continue

        if confirmed in new_map and len(text) <= len(new_map[confirmed]):
            # Conservar el bloque más largo si hay colisión de roles.
            pass
        else:
            if confirmed in new_map and new_map[confirmed].strip():
                # Concatenar si el usuario asignó dos bloques al mismo rol.
                if text not in new_map[confirmed]:
                    new_map[confirmed] = f"{new_map[confirmed].rstrip()}\n\n{text.strip()}"
            else:
                new_map[confirmed] = text.strip()

        detected_as = override.get("detected_as") or ROLE_LABELS.get(confirmed, confirmed)
        titles = list(new_meta.get(confirmed, {}).get("detected_titles") or [])
        if detected_as not in titles:
            titles.append(detected_as)
        new_meta[confirmed] = {
            **(meta.get(original) or meta.get(confirmed) or {}),
            "detected_titles": titles,
            "user_confirmed": True,
            "confidence": "high",
        }
        remapped_index.append(
            {
                "role": confirmed,
                "title": detected_as,
                "words": count_words(new_map[confirmed]),
                "page": (meta.get(original) or {}).get("index_page"),
            }
        )

    # Conservar bloques no editados que no fueron omitidos explícitamente.
    touched_originals = {o.get("role_original") for o in overrides}
    for role, text in role_texts.items():
        if role in touched_originals:
            continue
        if role in new_map or not text.strip():
            continue
        if role in ROLE_LABELS and role not in {"otros", "omitir"}:
            new_map[role] = text
            new_meta[role] = dict(meta.get(role) or {"detected_titles": [ROLE_LABELS[role]]})

    parsed = dict(parsed)
    parsed["section_map"] = new_map
    parsed["section_meta"] = new_meta
    parsed["structure_confirmed"] = True
    if remapped_index:
        # Recalcular porcentajes para vista.
        total = max(sum(item["words"] for item in remapped_index), 1)
        for item in remapped_index:
            pct = round(item["words"] * 100 / total, 1)
            item["percent"] = pct
            item["percent_label"] = f"{pct:.1f}%"
        parsed["index_sections"] = remapped_index
        if parsed.get("structure_source") != "index":
            parsed["structure_source"] = "confirmed"
    return parsed


def structure_confidence_summary(sections: list[dict]) -> dict:
    levels = [s.get("confidence") for s in sections]
    return {
        "total": len(sections),
        "high": sum(1 for c in levels if c == "high"),
        "medium": sum(1 for c in levels if c == "medium"),
        "low": sum(1 for c in levels if c == "low"),
        "needs_review": sum(1 for c in levels if c in {"low", "medium"}) > 0,
    }


MANUAL_OUTLINE_PLACEHOLDER = """Pegue aquí el índice o la lista de apartados (un título por línea).
Opcional: agregue el rol canónico separado por | 

Ejemplo (mejor que pegar el índice completo del PDF):
RESUMEN | presentacion
CAPÍTULO I: EFECTOS BENÉFICOS DE Trichoderma | marco_teorico
CAPÍTULO II: Trichoderma virens Y PRODUCCIÓN ENZIMÁTICA | marco_teorico
CAPÍTULO III | objetivos
OBJETIVO GENERAL | objetivos
CAPÍTULO IV: CARACTERIZACIÓN DE UN NUEVO FACTOR | introduccion
INTRODUCCIÓN | introduccion
MÉTODOS | metodologia
RESULTADOS | resultados
DISCUSIÓN | discusion
REFERENCIAS | bibliografia
"""

_ROLE_ALIASES_MANUAL = {
    "presentacion": "presentacion",
    "presentación": "presentacion",
    "resumen": "presentacion",
    "abstract": "presentacion",
    "introduccion": "introduccion",
    "introducción": "introduccion",
    "objetivos": "objetivos",
    "objetivo": "objetivos",
    "marco": "marco_teorico",
    "marco_teorico": "marco_teorico",
    "marco teórico": "marco_teorico",
    "metodologia": "metodologia",
    "metodología": "metodologia",
    "metodos": "metodologia",
    "métodos": "metodologia",
    "resultados": "resultados",
    "discusion": "discusion",
    "discusión": "discusion",
    "discusiones": "discusion",
    "conclusiones": "conclusiones",
    "conclusión": "conclusiones",
    "bibliografia": "bibliografia",
    "bibliografía": "bibliografia",
    "referencias": "bibliografia",
    "otros": "otros",
    "omitir": "omitir",
}


def _normalize_manual_role(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return "otros"
    if raw in ROLE_LABELS:
        return raw
    mapped = _ROLE_ALIASES_MANUAL.get(raw)
    if mapped:
        return mapped
    # Etiqueta canónica completa
    for role, label in ROLE_LABELS.items():
        if label.lower() == raw:
            return role
    from savt.section_resolver import classify_heading

    return classify_heading(value) or "otros"


def _strip_toc_page_number(line: str) -> str:
    """Quita número de página al final (arábigo o romano), sin romper «CAPÍTULO I»."""
    text = line.strip()
    if re.search(r"(?i)cap[ií]tulo\s+[ivxlcdm\d]+", text):
        return re.sub(r"\s+\d{1,4}$", "", text).strip()
    return re.sub(r"\s+(?:\d{1,4}|[IVXLCDM]{1,8})$", "", text).strip()


def _is_toc_noise_title(title: str) -> bool:
    folded = _fold_accents(title).strip().lower()
    if not folded:
        return True
    if re.fullmatch(r"\d+|[ivxlcdm]+", folded):
        return True
    noise = {
        "tabla de contenido",
        "tabla de contenidos",
        "contenido",
        "indice",
        "índice",
        "index",
        "pagina",
        "página",
        "paginas",
        "páginas",
    }
    return folded in noise


def _looks_like_heading_start(line: str) -> bool:
    return bool(
        re.match(
            r"(?i)^(?:"
            r"cap[ií]tulo|cap\.\s*|resumen|abstract|agradecimientos?|"
            r"introducci[oó]n|objetivo|justificaci[oó]n|hip[oó]tesis|"
            r"marco|metodolog|materiales|m[eé]todos|resultados|"
            r"discusi[oó]n|conclusi[oó]n|referencias|bibliograf|"
            r"anexos?|ap[eé]ndice|\d+(?:\.\d+)*\.?\s+[A-ZÁÉÍÓÚÑ]"
            r")",
            line.strip(),
        )
    )


def _looks_like_line_continuation(prev: str, current: str) -> bool:
    if not prev or not current:
        return False
    if _looks_like_heading_start(current):
        return False
    if re.fullmatch(r"\d+|[IVXLCDM]+", current.strip()):
        return True  # página suelta → se limpia luego; no fusionar como título
    prev_stripped = prev.rstrip()
    if prev_stripped.endswith((":", ";", ",", "—", "-")):
        return True
    if re.search(r"(?i)\b(y|de|del|la|el|los|las|su|sus|un|una|para|con|en)\s*$", prev_stripped):
        return True
    # Línea corta en mayúsculas tras un título incompleto
    if len(current) < 48 and current.upper() == current and not _looks_like_heading_start(current):
        return True
    return False


def clean_pasted_toc(text: str, *, major_only: bool = False) -> str:
    """
    Normaliza un índice pegado desde PDF: une líneas partidas, quita páginas
    y entradas de ruido (TABLA DE CONTENIDO, números sueltos).
    """
    if not text or not text.strip():
        return ""

    raw_lines = [ln.strip() for ln in text.splitlines()]
    merged: list[str] = []
    for line in raw_lines:
        if not line or line.startswith("#"):
            continue
        if re.fullmatch(r"\d+|[IVXLCDM]+", line):
            continue
        line = re.sub(r"[.\u2026…]{2,}\s*\S+\s*$", "", line).strip()
        probe = _strip_toc_page_number(re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", line).strip())
        if _is_toc_noise_title(probe):
            continue
        if merged and _looks_like_line_continuation(merged[-1], line):
            merged[-1] = f"{merged[-1]} {line}".strip()
        else:
            merged.append(line)

    cleaned: list[str] = []
    for line in merged:
        if "|" in line:
            title_part, role_part = line.split("|", 1)
            title = _strip_toc_page_number(title_part.strip())
            role = role_part.strip()
            line_out = f"{title} | {role}" if role else title
        else:
            # «1. INTRODUCCIÓN 2» → quitar numeración de entrada y página
            line = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", line).strip()
            title = _strip_toc_page_number(line)
            line_out = title

        title_only = line_out.split("|", 1)[0].strip()
        # Si al fusionar quedó ruido al final, cortar
        title_only = re.split(r"(?i)\s+TABLA DE CONTENIDO\b.*$", title_only)[0].strip()
        line_out = (
            f"{title_only} | {line_out.split('|', 1)[1].strip()}"
            if "|" in line_out
            else title_only
        )
        if len(title_only) < 3 or _is_toc_noise_title(title_only):
            continue
        if major_only and not _looks_like_heading_start(title_only):
            continue
        cleaned.append(line_out)

    return "\n".join(cleaned)


def parse_manual_outline(text: str) -> list[dict]:
    """
    Parsea líneas de índice/estructura manual.
    Formatos:
      - Título
      - Título | rol
      - 1. Título | metodologia
    Acepta pegados imperfectos de PDF (líneas partidas / números de página).
    """
    from savt.section_resolver import classify_heading

    entries: list[dict] = []
    normalized = clean_pasted_toc(text or "")
    if not normalized.strip():
        return entries

    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "|" in line:
            title_part, role_part = line.split("|", 1)
            title = title_part.strip()
            role = _normalize_manual_role(role_part.strip())
        else:
            title = line
            role = classify_heading(title) or "otros"
            if role == "otros":
                if re.match(r"(?i)^cap[ií]tulo\b", title):
                    role = "marco_teorico"
                elif re.match(r"(?i)^(?:referencias|bibliograf)", title):
                    role = "bibliografia"
                elif re.match(r"(?i)^agradecimientos?\b", title):
                    role = "omitir"

        if len(title) < 3 or _is_toc_noise_title(title):
            continue
        entries.append(
            {
                "title": title[:220],
                "role": role,
                "include": role != "omitir",
            }
        )
    return entries


_ROMAN_ARABIC = {
    "I": "1",
    "II": "2",
    "III": "3",
    "IV": "4",
    "V": "5",
    "VI": "6",
    "VII": "7",
    "VIII": "8",
    "IX": "9",
    "X": "10",
    "XI": "11",
    "XII": "12",
}
_ARABIC_ROMAN = {v: k for k, v in _ROMAN_ARABIC.items()}


def _fold_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _char_class(ch: str) -> str:
    """Clase regex que tolera mayúsculas/minúsculas y acentos frecuentes."""
    base = _fold_accents(ch).upper()
    variants = {
        "A": "AÁÀÄÂaáàäâ",
        "E": "EÉÈËÊeéèëê",
        "I": "IÍÌÏÎiíìïî",
        "O": "OÓÒÖÔoóòöô",
        "U": "UÚÙÜÛuúùüû",
        "N": "NÑnñ",
        "C": "CÇcç",
    }
    if base in variants:
        return f"[{variants[base]}]"
    if ch.isalnum():
        return f"[{re.escape(ch.upper())}{re.escape(ch.lower())}]"
    return re.escape(ch)


def _token_to_pattern(token: str, *, after_capitulo: bool = False) -> str:
    raw = token.strip().rstrip(".:;,—–-")
    if not raw:
        return ""
    folded = _fold_accents(raw).upper()
    if after_capitulo:
        roman = folded.strip(".")
        if roman in _ROMAN_ARABIC:
            arab = _ROMAN_ARABIC[roman]
            return rf"(?:{roman}|{arab})\.?"
        if roman in _ARABIC_ROMAN:
            rom = _ARABIC_ROMAN[roman]
            return rf"(?:{rom}|{roman})\.?"
    if folded in {"CAPITULO", "CAPÍTULO"}:
        return r"CAP[IÍ]TULO"
    return "".join(_char_class(ch) for ch in raw)


def _flexible_title_pattern(title: str, *, loose: bool = False) -> re.Pattern[str]:
    words = [w for w in re.split(r"\s+", title.strip()) if w]
    if not words:
        return re.compile(r"(?!x)x")
    # Usar primeras palabras para tolerar títulos partidos / truncados en PDF
    limit = 4 if loose else (8 if len(words) > 8 else len(words))
    core = words[:limit]
    parts: list[str] = []
    prev_capitulo = False
    for word in core:
        part = _token_to_pattern(word, after_capitulo=prev_capitulo)
        if not part:
            continue
        parts.append(part)
        folded = _fold_accents(word).upper().rstrip(".:")
        prev_capitulo = folded in {"CAPITULO", "CAPÍTULO"}
    if not parts:
        return re.compile(r"(?!x)x")
    joined = r"\s+".join(parts)
    # Ancla por límite de palabra (no solo inicio de línea): en índices PDF
    # varios títulos pueden ir en la misma línea.
    return re.compile(rf"(?is)(?<![A-Za-zÁÉÍÓÚÜÑáéíóúüñ])(?:[IVXLC\d]{{1,6}}\s+)?{joined}")


def _looks_like_toc_hit(body: str, pos: int) -> bool:
    """Detecta títulos embebidos en la tabla de contenido (varios encabezados seguidos)."""
    body_len = max(len(body), 1)
    following = body[pos : pos + 160]
    headers_after = re.findall(
        r"(?i)\b(?:"
        r"CAP[IÍ]TULO|REFERENCIAS|BIBLIOGRAF[IÍ]A|FIGURAS|TABLAS|ABSTRACT|"
        r"RESUMEN|INTRODUCCI[OÓ]N|M[EÉ]TODOS|MATERIALES|RESULTADOS|"
        r"DISCUSI[OÓ]N(?:ES)?|CONCLUSI[OÓ]N(?:ES)?|OBJETIVOS?|JUSTIFICACI[OÓ]N|"
        r"HIP[OÓ]TESIS|ANEXOS?"
        r")\b",
        following,
    )
    lowercase_words = re.findall(r"\b[a-záéíóúüñ]{4,}\b", following)
    # En el índice suelen encadenarse apartados con poca prosa en minúsculas
    if len(headers_after) >= 3 and len(lowercase_words) <= 4:
        return True
    # Zona temprana: dos encabezados seguidos (p. ej. OBJETIVOS … CAPITULO IV) = TOC
    if (
        pos < int(body_len * 0.12)
        and len(headers_after) >= 2
        and len(lowercase_words) <= 6
        and re.search(r"(?i)\bCAP[IÍ]TULO\b", following)
    ):
        return True
    # Línea típica de TOC: título + puntos + número de página
    line_end = body.find("\n", pos)
    line = body[pos : line_end if line_end != -1 else pos + 100]
    if re.search(r"[.\u2026…]{2,}\s*\d+\s*$", line):
        return True
    return False


def _heading_score(body: str, pos: int, *, body_len: int, min_pos: int) -> int:
    """Prioriza coincidencias de cuerpo (no índice) y títulos al inicio de línea."""
    score = 0
    if pos >= min_pos:
        score += 20
    if pos >= int(body_len * 0.08):
        score += 12
    if pos >= int(body_len * 0.12):
        score += 8
    prev = body[max(0, pos - 2) : pos]
    if "\n" in prev or pos == 0:
        score += 10
    # Línea relativamente corta → más probable que sea encabezado
    line_end = body.find("\n", pos)
    line = body[pos : line_end if line_end != -1 else min(pos + 160, body_len)]
    if len(line.strip()) <= 120:
        score += 6
    if len(line.strip()) <= 60:
        score += 4
    if _looks_like_toc_hit(body, pos):
        score -= 40
    return score


def locate_title_in_text(
    body: str,
    title: str,
    *,
    min_pos: int = 0,
    occupied: list[tuple[int, int]] | None = None,
) -> int | None:
    """Busca el título declarado por el usuario en el cuerpo del documento."""
    if not body or not title:
        return None

    matches = list(_flexible_title_pattern(title).finditer(body))
    if not matches:
        words = title.split()
        if len(words) >= 2:
            matches = list(_flexible_title_pattern(title, loose=True).finditer(body))
    if not matches and len(title.split()) >= 3:
        short = " ".join(title.split()[:3])
        matches = list(_flexible_title_pattern(short, loose=True).finditer(body))
    if not matches:
        return None

    occupied = occupied or []

    def _is_free(pos: int) -> bool:
        for start, end in occupied:
            if start - 30 <= pos <= end + 30:
                return False
        return True

    body_len = max(len(body), 1)
    free = [m for m in matches if _is_free(m.start())]
    if not free:
        return None

    # Preferir apariciones reales del cuerpo; si solo hay hits de TOC, no usarlos
    body_hits = [m for m in free if not _looks_like_toc_hit(body, m.start())]
    pool_src = body_hits if body_hits else []
    if not pool_src:
        # Título solo en índice → mejor reportarlo como no localizado
        return None

    ranked = sorted(
        pool_src,
        key=lambda m: (
            -_heading_score(body, m.start(), body_len=body_len, min_pos=min_pos),
            m.start() if m.start() >= min_pos else body_len + m.start(),
        ),
    )
    pool = [m for m in ranked if m.start() >= min_pos] or ranked
    if len(pool) >= 2 and all(m.start() < int(body_len * 0.15) for m in pool):
        return max(pool, key=lambda m: m.start()).start()
    return pool[0].start()


def apply_manual_outline(parsed: dict, entries: list[dict]) -> dict:
    """
    Localiza en el texto cada título ingresado por el usuario y arma section_map.
    Los bloques se cortan desde un título hasta el siguiente.
    """
    body = parsed.get("body") or parsed.get("full_text") or ""
    if not body or not entries:
        return parsed

    active = [e for e in entries if e.get("include", True) and e.get("role") != "omitir"]
    if not active:
        return parsed

    located: list[tuple[int, dict]] = []
    occupied: list[tuple[int, int]] = []
    cursor = 0
    for entry in active:
        title = str(entry.get("title") or "")
        # Preferir orden del índice; si no aparece después del cursor, buscar en todo el doc
        # (p. ej. bibliografías de capítulos previos).
        pos = locate_title_in_text(body, title, min_pos=cursor, occupied=occupied)
        if pos is None and cursor > 0:
            pos = locate_title_in_text(body, title, min_pos=0, occupied=occupied)
        if pos is None:
            continue
        located.append((pos, entry))
        occupied.append((pos, pos + max(len(title), 8)))
        cursor = max(cursor, pos + 5)

    located.sort(key=lambda item: item[0])
    # Deduplicar posiciones casi iguales
    unique: list[tuple[int, dict]] = []
    for pos, entry in located:
        if unique and pos - unique[-1][0] < 15:
            continue
        unique.append((pos, entry))

    section_map: dict[str, str] = {}
    section_meta: dict[str, dict] = {}
    index_sections: list[dict] = []
    missing: list[str] = []

    found_titles = {e.get("title") for _, e in unique}
    for entry in active:
        if entry.get("title") not in found_titles:
            missing.append(str(entry.get("title")))

    for idx, (pos, entry) in enumerate(unique):
        end = unique[idx + 1][0] if idx + 1 < len(unique) else len(body)
        chunk = body[pos:end].strip()
        words = count_words(chunk)
        if words < 20:
            continue
        role = entry.get("role") or "otros"
        title = str(entry.get("title") or ROLE_LABELS.get(role, role))
        if role in {"otros"}:
            key = f"otros_{idx + 1}"
            section_map[key] = chunk
            section_meta[key] = {
                "detected_titles": [title],
                "user_confirmed": True,
                "manual": True,
            }
            index_sections.append(
                {"role": "otros", "title": title, "words": words, "manual": True}
            )
            continue

        if role in section_map and section_map[role].strip():
            if chunk not in section_map[role]:
                section_map[role] = f"{section_map[role].rstrip()}\n\n{chunk}"
            titles = list(section_meta[role].get("detected_titles") or [])
            if title not in titles:
                titles.append(title)
            section_meta[role]["detected_titles"] = titles
        else:
            section_map[role] = chunk
            section_meta[role] = {
                "detected_titles": [title],
                "user_confirmed": True,
                "manual": True,
                "confidence": "high",
            }
        index_sections.append(
            {
                "role": role,
                "title": title,
                "words": words,
                "manual": True,
            }
        )

    total = max(sum(int(i.get("words") or 0) for i in index_sections), 1)
    for item in index_sections:
        pct = round(int(item.get("words") or 0) * 100 / total, 1)
        item["percent"] = pct
        item["percent_label"] = f"{pct:.1f}%"

    parsed = dict(parsed)
    parsed["section_map"] = section_map
    parsed["section_meta"] = section_meta
    parsed["index_sections"] = index_sections
    parsed["structure_source"] = "manual"
    parsed["structure_confirmed"] = True
    parsed["manual_missing_titles"] = missing
    return parsed


CANONICAL_TEMPLATE_OUTLINE = """RESUMEN | presentacion
INTRODUCCIÓN | introduccion
OBJETIVO GENERAL | objetivos
OBJETIVOS ESPECÍFICOS | objetivos
MARCO TEÓRICO | marco_teorico
METODOLOGÍA | metodologia
MATERIALES Y MÉTODOS | metodologia
RESULTADOS | resultados
DISCUSIÓN | discusion
CONCLUSIONES | conclusiones
REFERENCIAS | bibliografia
BIBLIOGRAFÍA | bibliografia
"""

