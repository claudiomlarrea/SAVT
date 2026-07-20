"""Árbol jerárquico de tesis (capítulos → secciones) y detección de tipo.

Uso de emergencia: tesis por compendio/capítulos sin aplanar todo a una lista canónica.
"""

from __future__ import annotations

import re
import unicodedata

from savt.section_resolver import classify_heading
from savt.word_stats import count_words

_BODY_CAPITULO = re.compile(
    r"(?im)(?:^|\n)\s*CAP[IÍ]TULO\s+([IVXLC]+|\d{1,2})\b([^\n]*)",
)

_MAJOR_SECTION = re.compile(
    r"(?im)^(?:"
    r"ABSTRACT|RESUMEN|"
    r"INTRODUCCI[ÓO]N|"
    r"JUSTIFICACI[ÓO]N|"
    r"HIP[ÓO]TESIS|"
    r"OBJETIVO(?:S)?(?:\s+GENERAL(?:ES)?)?|"
    r"OBJETIVOS?\s+ESPEC[IÍ]FICOS?|"
    r"OBJETIVOS?\s+PARTICULARES?|"
    r"MARCO\s+TE[ÓO]RICO|"
    r"MATERIALES?\s+Y\s+M[EÉ]TODOS?|"
    r"M[EÉ]TODOS?|"
    r"METODOLOG[IÍ]A|"
    r"RESULTADOS?|"
    r"DISCUSI[ÓO]N(?:ES)?|"
    r"CONCLUSI[ÓO]N(?:ES)?|"
    r"REFERENCIAS|BIBLIOGRAF[IÍ]A"
    r")\s*$"
)

# «1. INTRODUCCIÓN» / «2. EL GÉNERO…» (un nivel, no 3.1)
_NUMBERED_TOP = re.compile(
    r"(?m)^(\d{1,2})\.\s+([A-ZÁÉÍÓÚÑ][^\n]{3,120})$"
)

# «1. INTRODUCCIÓN Las especies…» (título y cuerpo en la misma línea — habitual en PDF)
_INLINE_SECTION_HEAD = re.compile(
    r"(?im)^(\d{1,2})\.\s+"
    r"(INTRODUCCIÓN|INTRODUCCION|"
    r"MATERIALES?\s+Y\s+M[EÉ]TODOS?|"
    r"M[EÉ]TODOS?|METODOLOG[IÍ]A|"
    r"RESULTADOS?|DISCUSI[ÓO]N(?:ES)?|"
    r"CONCLUSI[ÓO]N(?:ES)?|"
    r"REFERENCIAS|BIBLIOGRAF[IÍ]A|"
    r"JUSTIFICACI[ÓO]N|"
    r"OBJETIVOS?(?:\s+ESPEC[IÍ]FICOS?|\s+GENERAL(?:ES)?)?|"
    r"MARCO\s+TE[ÓO]RICO|"
    r"ABSTRACT|RESUMEN|"
    r"HIP[ÓO]TESIS"
    r")\b\s+(?=[A-ZÁÉÍÓÚÑ\"«(])"
)

_NEXT_SECTION_BOUNDARY = re.compile(
    r"(?im)(?:"
    r"^\d{1,2}\.\s+(?:INTRODUCCI|MATERIAL|M[EÉ]TODO|METODOLOG|RESULTADO|DISCUSI|CONCLUSI|"
    r"REFERENC|BIBLIOGRAF|JUSTIFICAC|OBJETIV|MARCO\s+TE|ABSTRACT|RESUMEN|HIP[ÓO]TESIS)\b"
    r"|^\d{1,2}\.\s+[A-ZÁÉÍÓÚÑ][^\n]{3,120}$"
    r")"
)

_FALSE_TITLE = re.compile(
    r"(?i)^(?:"
    r"y\s+\w+|"  # «y hemicelulasa»
    r"de\s+la\s+\w+|"
    r"del\s+\w+|"
    r"\d+\s+bio-protection|"
    r"lincoln\s+university|"
    r"https?://|"
    r"figura\s+\d+|tabla\s+\d+"
    r")"
)


def _fold(text: str) -> str:
    norm = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")


def _roman_or_digit_to_int(token: str) -> int | None:
    token = (token or "").strip().lower()
    if token.isdigit() and 1 <= int(token) <= 20:
        return int(token)
    mapping = {
        "i": 1,
        "ii": 2,
        "iii": 3,
        "iv": 4,
        "v": 5,
        "vi": 6,
        "vii": 7,
        "viii": 8,
        "ix": 9,
        "x": 10,
    }
    return mapping.get(token)


def is_false_heading(title: str) -> bool:
    """Rechaza fragmentos que no son encabezados reales."""
    t = (title or "").strip()
    if len(t) < 4:
        return True
    if len(t) > 180:
        return True
    if _FALSE_TITLE.match(t):
        return True
    # Empieza en minúscula y no es numerado → casi seguro prosa partida
    if t[0].islower() and not re.match(r"^\d+\.", t):
        return True
    # Solo conectores / restos
    if re.fullmatch(r"(?i)(?:y|de|del|la|el|los|las|un|una|en|con|por)\s+\S{1,30}", t):
        return True
    # Líneas de bibliografía / citas coladas como «51. Shoresh M…»
    if re.search(r"\(\d{4}\)", t):
        return True
    if re.search(r"(?i)\bet\s+al\.?\b|doi:|https?://|phytopathol|\bpp\.\s*\d", t):
        return True
    if re.match(
        r"^\d+\.\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-Z]\.?){0,4}\s*[,;]",
        t,
    ):
        return True
    # «7. REFERENCIAS Alfano G., …» (TOC/ruido + autores)
    if re.match(r"(?i)^\d+\.\s+referencias\b", t) and (
        "," in t or re.search(r"[A-Z]\.\s*[A-Z]", t)
    ):
        return True
    # Abstract de paper citado, no sección
    if re.match(r"(?i)^abstract\.\s+\w+", t):
        return True
    return False


def _clean_chapter_title(title_tail: str) -> str:
    """Evita que el título del capítulo arrastre la primera frase del cuerpo."""
    t = re.sub(r"\s+", " ", (title_tail or "").strip(" :.-–"))
    if not t:
        return t
    # Solo cortar prosa típica tras título en mayúsculas: «JUSTIFICACIÓN La capacidad…»
    # (no cortar nombres científicos: «… DE Trichoderma»)
    parts = re.split(
        r"\s+(?=(?:La|El|Los|Las|Una|Un)\s+[a-záéíóúñ])",
        t,
        maxsplit=1,
    )
    t = parts[0].strip(" :.-")
    return (t[:140] if len(t) >= 3 else (title_tail or "").strip()[:100])


def select_body_capitulo_boundaries(full_text: str) -> list[tuple[int, int, str]]:
    """
    Devuelve [(num, pos, title_tail), ...] de CAPÍTULOS en el cuerpo
    (evita repeticiones del índice).
    """
    if not full_text:
        return []
    matches = list(_BODY_CAPITULO.finditer(full_text))
    if len(matches) < 2:
        return []

    by_num: dict[int, list[re.Match[str]]] = {}
    for match in matches:
        num = _roman_or_digit_to_int(match.group(1))
        if num is None:
            continue
        by_num.setdefault(num, []).append(match)

    selected: list[tuple[int, int, str]] = []
    for num in sorted(by_num):
        opts = by_num[num]
        chosen = opts[-1] if len(opts) > 1 else opts[0]
        if len(opts) > 1 and opts[0].start() < len(full_text) * 0.12:
            chosen = opts[-1]
        title_tail = _clean_chapter_title((chosen.group(2) or "").strip(" :.-–"))
        if len(title_tail) < 8:
            after = full_text[chosen.end() : chosen.end() + 300]
            nxt = re.search(r"(?m)^\s*([A-ZÁÉÍÓÚÑ][^\n]{12,160})", after)
            title_tail = _clean_chapter_title(nxt.group(1).strip() if nxt else f"Capítulo {num}")
        selected.append((num, chosen.start(), title_tail[:160]))

    if len(selected) >= 3 and selected[0][1] < len(full_text) * 0.08 and len(matches) >= 6:
        selected = []
        for num in sorted(by_num):
            chosen = by_num[num][-1]
            title_tail = _clean_chapter_title((chosen.group(2) or "").strip(" :.-–"))
            if len(title_tail) < 8:
                after = full_text[chosen.end() : chosen.end() + 300]
                nxt = re.search(r"(?m)^\s*([A-ZÁÉÍÓÚÑ][^\n]{12,160})", after)
                title_tail = _clean_chapter_title(nxt.group(1).strip() if nxt else f"Capítulo {num}")
            selected.append((num, chosen.start(), title_tail[:160]))

    return sorted(selected, key=lambda item: item[1])


def detect_thesis_type(full_text: str, *, structure_source: str = "") -> str:
    """'compendio' si hay varios CAPÍTULOS de cuerpo; si no, 'clasica'."""
    boundaries = select_body_capitulo_boundaries(full_text or "")
    if len(boundaries) >= 3 or structure_source == "capitulos":
        return "compendio"
    return "clasica"


def _looks_like_chapter_toc(chunk: str, pos: int, body_start: int) -> bool:
    """Mini-índice al inicio del capítulo (líneas numeradas sin prosa)."""
    if pos > min(1200, len(chunk) // 4):
        return False
    after = chunk[body_start : body_start + 120]
    if re.match(r"(?m)^\s*\d+\.\s+[A-Z]", after):
        return True
    snippet = chunk[pos : pos + 450]
    numbered = len(re.findall(r"(?m)^\s*\d+\.\s+\S", snippet))
    lowercase = len(re.findall(r"[a-záéíóúñ]", snippet))
    return numbered >= 3 and lowercase < 90


def _section_end_relative(chunk: str, body_start: int, section_num: str | None = None) -> int:
    rest = chunk[body_start:]
    candidates: list[int] = []
    if section_num and str(section_num).isdigit():
        n = int(section_num)
        m = re.search(rf"(?im)\n{n + 1}\.\s+\S", rest)
        if m and m.start() >= 15:
            candidates.append(m.start())
    m = re.search(r"(?im)\n\d{1,2}\.\s+[A-ZÁÉÍÓÚÑ]", rest)
    if m and m.start() >= 15:
        candidates.append(m.start())
    match = _NEXT_SECTION_BOUNDARY.search(rest)
    if match and match.start() >= 25:
        candidates.append(match.start())
    if candidates:
        return body_start + min(candidates)
    return len(chunk)


ACADEMIC_SUBSECTION_ROLES = frozenset(
    {
        "introduccion",
        "objetivos",
        "metodologia",
        "resultados",
        "discusion",
        "conclusiones",
    }
)


def aggregate_role_text_from_tree(parsed: dict, role: str) -> str:
    """Texto agregado de subsecciones del árbol con un rol académico (p. ej. introduccion)."""
    tree = parsed.get("structure_tree") or []
    full_text = parsed.get("full_text") or parsed.get("body") or ""
    if not tree or not full_text or not role:
        return ""
    parts: list[str] = []
    for node in tree:
        for child in node.get("children") or []:
            if str(child.get("role") or "") != role:
                continue
            start, end = child.get("start"), child.get("end")
            if start is None or end is None:
                continue
            text = full_text[int(start) : int(end)].strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def _child_headings_in_chunk(chunk: str, *, abs_start: int) -> list[dict]:
    """Secciones mayores (nivel 2) dentro de un capítulo; no 3.1 / 3.1.1."""
    spans: list[dict] = []

    for match in _INLINE_SECTION_HEAD.finditer(chunk):
        num = match.group(1)
        heading = re.sub(r"\s+", " ", (match.group(2) or "").strip())
        title = f"{num}. {heading}"
        body_start = match.end()
        if _looks_like_chapter_toc(chunk, match.start(), body_start):
            continue
        end = _section_end_relative(chunk, body_start, section_num=num)
        text = chunk[match.start() : end].strip()
        if count_words(text) < 40:
            continue
        spans.append(
            {
                "start": match.start(),
                "end": end,
                "title": title,
                "kind": "inline",
            }
        )

    found: list[tuple[int, str, str]] = []

    for match in _MAJOR_SECTION.finditer(chunk):
        title = re.sub(r"\s+", " ", match.group(0).strip())
        if is_false_heading(title):
            continue
        # «ABSTRACT» seguido de prosa/cita no es el encabezado de sección
        if re.match(r"(?i)^abstract\b.+\.", title) and len(title) > 20:
            continue
        if re.match(r"(?i)^referencias\b.+,", title):
            continue
        # Evitar hits en el mini-índice al inicio del capítulo (poca prosa)
        if match.start() < min(400, len(chunk) // 20):
            window = chunk[match.start() : match.start() + 120]
            if len(re.findall(r"(?i)\b(?:abstract|introducci|m[eé]todos|resultados|discusi|referencias)\b", window)) >= 3:
                continue
        found.append((match.start(), title, "major"))

    for match in _NUMBERED_TOP.finditer(chunk):
        num = match.group(1)
        rest = match.group(2).strip()
        title = f"{num}. {rest}"
        if is_false_heading(rest) or is_false_heading(title):
            continue
        # Preferir títulos de sección (mayúsculas / palabras clave), no prosa
        caps_ratio = sum(1 for ch in rest if ch.isupper()) / max(sum(1 for ch in rest if ch.isalpha()), 1)
        if caps_ratio < 0.45 and not re.match(
            r"(?i)^(introducci|material|m[eé]todo|resultado|discusi|conclusi|referenc|objetivo|hip[oó]tesis|justificaci|marco|abstract|resumen)",
            rest,
        ):
            continue
        found.append((match.start(), title, "numbered"))

    found.sort(key=lambda item: item[0])
    merged: list[tuple[int, str, str]] = []
    for item in found:
        if merged and item[0] - merged[-1][0] < 20:
            continue
        merged.append(item)

    for idx, (pos, title, kind) in enumerate(merged):
        end = merged[idx + 1][0] if idx + 1 < len(merged) else len(chunk)
        if any(s["start"] <= pos < s["end"] for s in spans):
            continue
        spans.append({"start": pos, "end": end, "title": title, "kind": kind})

    spans.sort(key=lambda s: s["start"])
    deduped: list[dict] = []
    for span in spans:
        if deduped and span["start"] - deduped[-1]["start"] < 15:
            if (span["end"] - span["start"]) > (deduped[-1]["end"] - deduped[-1]["start"]):
                deduped[-1] = span
            continue
        deduped.append(span)

    children: list[dict] = []
    for span in deduped:
        pos, end, title, kind = span["start"], span["end"], span["title"], span["kind"]
        text = chunk[pos:end].strip()
        words = count_words(text)
        if words < 40:
            continue
        role = classify_heading(title) or "otros"
        if role == "otros" and re.match(r"(?i)^\d+\.\s+introducci", title):
            role = "introduccion"
        children.append(
            {
                "level": 2,
                "title": title,
                "role": role,
                "words": words,
                "start": abs_start + pos,
                "end": abs_start + end,
                "kind": kind,
                "children": [],
            }
        )
    return children


def build_structure_tree(full_text: str) -> list[dict]:
    """Árbol: nodos nivel 1 = CAPÍTULOS; hijos = secciones mayores."""
    boundaries = select_body_capitulo_boundaries(full_text)
    if len(boundaries) < 2:
        return []

    tree: list[dict] = []
    for idx, (num, pos, title_tail) in enumerate(boundaries):
        end = boundaries[idx + 1][1] if idx + 1 < len(boundaries) else len(full_text)
        chunk = full_text[pos:end].strip()
        words = count_words(chunk)
        if words < 80:
            continue
        display = f"CAPÍTULO {num}: {title_tail}" if title_tail else f"CAPÍTULO {num}"
        role = classify_heading(display) or "otros"
        if role == "otros":
            if num <= 2:
                role = "marco_teorico"
            elif re.search(r"(?i)objetivo|hip[oó]tesis|justificaci", chunk[:2500]):
                role = "objetivos"
            else:
                role = "otros"
        children = _child_headings_in_chunk(chunk, abs_start=pos)
        tree.append(
            {
                "level": 1,
                "chapter_num": num,
                "title": display,
                "role": role,
                "words": words,
                "start": pos,
                "end": end,
                "children": children,
            }
        )
    return tree


def flatten_tree_for_display(tree: list[dict], *, include_children: bool = True) -> list[dict]:
    """
    Lista para UI/CSV.
    - Capítulos con % del documento.
    - Hijos con ruta «CAPÍTULO N › Sección» (no se usan para sumar 100% juntos:
      el % del hijo es respecto del documento; el capítulo también).
    Por defecto solo capítulos en la tabla principal (include_children=False
    evita doble conteo visual); con True se listan rutas anidadas.
    """
    total = max(sum(int(n.get("words") or 0) for n in tree), 1)
    rows: list[dict] = []
    for node in tree:
        words = int(node.get("words") or 0)
        pct = round(words * 100 / total, 1)
        rows.append(
            {
                "role": node.get("role") or "otros",
                "title": node.get("title") or "—",
                "page": str(node.get("chapter_num") or ""),
                "words": words,
                "percent": pct,
                "percent_label": f"{pct:.1f}%",
                "level": 1,
                "path": node.get("title") or "—",
                "chapter_num": node.get("chapter_num"),
            }
        )
        if not include_children:
            continue
        for child in node.get("children") or []:
            cw = int(child.get("words") or 0)
            if cw < 60:
                continue
            # Solo secciones «paper» / mayor interés (no todos los 1. 2. 3. de revisión)
            title = str(child.get("title") or "")
            role = child.get("role") or "otros"
            keep = role in {
                "presentacion",
                "introduccion",
                "objetivos",
                "metodologia",
                "resultados",
                "discusion",
                "conclusiones",
                "bibliografia",
            } or bool(re.match(r"(?i)^(abstract|resumen|m[eé]todos|materiales|resultados|discusi|conclusi|referencias|objetivo|hip[oó]tesis)", title))
            if not keep:
                continue
            cpct = round(cw * 100 / total, 1)
            path = f"{node.get('title')} › {title}"
            rows.append(
                {
                    "role": role,
                    "title": path,
                    "page": str(node.get("chapter_num") or ""),
                    "words": cw,
                    "percent": cpct,
                    "percent_label": f"{cpct:.1f}%",
                    "level": 2,
                    "path": path,
                    "chapter_num": node.get("chapter_num"),
                    "parent_title": node.get("title"),
                }
            )
    return rows


def tree_to_section_map(tree: list[dict], full_text: str) -> tuple[dict[str, str], dict[str, dict]]:
    """Agrega texto por rol canónico para los evaluadores existentes."""
    section_map: dict[str, str] = {}
    section_meta: dict[str, dict] = {}

    def _add(role: str, title: str, start: int, end: int) -> None:
        if role in {"otros", "omitir"} or not role:
            return
        chunk = full_text[start:end].strip()
        if count_words(chunk) < 40:
            return
        if role in section_map:
            if chunk not in section_map[role]:
                section_map[role] = f"{section_map[role].rstrip()}\n\n{chunk}"
            titles = list(section_meta[role].get("detected_titles") or [])
            if title not in titles:
                titles.append(title)
            section_meta[role]["detected_titles"] = titles
        else:
            section_map[role] = chunk
            section_meta[role] = {"detected_titles": [title], "from_tree": True}

    for node in tree:
        _add(str(node.get("role")), str(node.get("title")), int(node["start"]), int(node["end"]))
        for child in node.get("children") or []:
            role = str(child.get("role") or "otros")
            if role == "otros":
                continue
            _add(role, str(child.get("title")), int(child["start"]), int(child["end"]))

    return section_map, section_meta
