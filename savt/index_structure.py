"""Partición del documento según el índice y conteo de palabras por apartado."""

from __future__ import annotations

import re

from savt.index_parser import (
    IndexEntry,
    bibliography_index_entry,
    index_pages_are_unreliable,
    is_capitulo_index_entries,
    parse_index_entries,
    top_level_index_entries,
)
from savt.section_resolver import classify_heading
from savt.word_stats import count_words

_HEADING_SKIP_FRAC = 0.10


def page_char_offsets(page_texts: list[str]) -> list[int]:
    """Posición de inicio de cada página en el texto concatenado."""
    offsets: list[int] = []
    pos = 0
    for idx, text in enumerate(page_texts):
        offsets.append(pos)
        pos += len(text)
        if idx < len(page_texts) - 1:
            pos += 1
    return offsets


def char_offset_for_page(page: int, offsets: list[int], text_len: int) -> int:
    if page <= 1:
        return 0
    if offsets and page <= len(offsets):
        return min(offsets[page - 1], text_len)
    if offsets:
        last_page = len(offsets)
        ratio = (page - 1) / max(last_page - 1, 1)
        return min(int(ratio * text_len), text_len)
    return min(int((page - 1) / 300 * text_len), text_len)


def _flexible_phrase(words: str) -> str:
    parts = words.split()
    if not parts:
        return ""
    return r"\s+".join(re.escape(part) for part in parts)


def _title_heading_patterns(entry: IndexEntry) -> list[re.Pattern[str]]:
    title = re.sub(r"\s+", " ", entry.title).strip()
    title_esc = re.escape(title)
    first_words = " ".join(title.split()[:4])
    first_words_esc = re.escape(first_words)
    first_words_flex = _flexible_phrase(first_words)
    num = re.escape(entry.number)
    patterns = [
        rf"(?im)^\s*{num}\.\s*{title_esc}\s*$",
        rf"(?im)^\s*{num}\.\s*{title_esc}",
        rf"(?im)^\s*{num}\.\s+{first_words_esc}",
        rf"(?im)^\s*cap[ií]tulo\s+{num}\s*[:.]\s*{title_esc}",
        rf"(?im)^\s*cap[ií]tulo\s+{num}\s*[:.]\s+{first_words_esc}",
        rf"(?is)cap[ií]tulo\s+{num}\s*[:.]\s+{first_words_flex}",
    ]
    if entry.is_bibliography:
        patterns.append(r"(?im)^\s*(?:\d+\.\s*)?BIBLIOGRAF[IÍA]\s*$")
    return [re.compile(p) for p in patterns]


def _find_heading_offset(
    full_text: str,
    entry: IndexEntry,
    *,
    min_pos: int,
    max_pos: int,
) -> int | None:
    """Localiza el encabezado real del apartado en el cuerpo (evita coincidencias en el índice)."""
    window = full_text[min_pos:max_pos]
    for pattern in _title_heading_patterns(entry):
        match = pattern.search(window)
        if match:
            return min_pos + match.start()
    return None


def _boundaries_from_headings(
    full_text: str,
    entries: list[IndexEntry],
) -> list[tuple[int, IndexEntry]]:
    """Posiciones por encabezados en el texto (robusto con páginas romanas)."""
    search_start = int(len(full_text) * _HEADING_SKIP_FRAC)
    boundaries: list[tuple[int, IndexEntry]] = []
    cursor = search_start

    for entry in entries:
        pos = _find_heading_offset(
            full_text,
            entry,
            min_pos=cursor,
            max_pos=len(full_text),
        )
        if pos is None and not boundaries:
            pos = _find_heading_offset(
                full_text,
                entry,
                min_pos=search_start,
                max_pos=len(full_text),
            )
        if pos is not None:
            boundaries.append((pos, entry))
            cursor = pos + max(20, len(entry.title))

    return sorted(boundaries, key=lambda item: item[0])


def _use_heading_locator(entries: list[IndexEntry]) -> bool:
    if is_capitulo_index_entries(entries):
        return True
    if any(entry.page_is_roman for entry in entries):
        return True
    if index_pages_are_unreliable(entries):
        return True
    return any(entry.page_label and not str(entry.page).isdigit() for entry in entries)


def _role_for_entry(entry: IndexEntry, used_roles: set[str]) -> str:
    role = entry.role or classify_heading(entry.title) or "otros"
    if role in used_roles and role != "otros":
        role = f"{role}_{entry.number}"
    used_roles.add(role.split("_")[0])
    return role


def index_layout_is_usable(layout: dict | None) -> bool:
    """Rechaza particiones de índice que concentran casi todo el texto en 1–2 bloques."""
    if not layout or layout.get("structure_source") != "index":
        return False
    sections = layout.get("index_sections") or []
    if len(sections) < 3:
        return False
    words = [max(0, int(item.get("words") or 0)) for item in sections]
    total = sum(words) or 1
    if max(words) / total >= 0.70:
        return False
    roles = {str(item.get("role") or "otros") for item in sections}
    canonical = roles & {
        "introduccion",
        "objetivos",
        "marco_teorico",
        "metodologia",
        "resultados",
        "discusion",
        "conclusiones",
        "presentacion",
    }
    if len(canonical) <= 1 and "otros" in roles and max(words) / total >= 0.50:
        return False
    return True


_BODY_CAPITULO = re.compile(
    r"(?im)(?:^|\n)\s*CAP[IÍ]TULO\s+([IVXLC]+|\d{1,2})\b([^\n]*)",
)


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


def partition_from_body_capitulos(full_text: str) -> dict | None:
    """
    Tesis por capítulos/artículos: localiza CAPÍTULOS en el cuerpo (no en el TOC),
    arma árbol jerárquico y mapa canónico para evaluadores.
    """
    if not full_text:
        return None

    from savt.structure_tree import (
        build_structure_tree,
        flatten_tree_for_display,
        select_body_capitulo_boundaries,
        tree_to_section_map,
    )

    boundaries = select_body_capitulo_boundaries(full_text)
    if len(boundaries) < 3:
        return None

    tree = build_structure_tree(full_text)
    if len(tree) < 3:
        return None

    section_map, section_meta = tree_to_section_map(tree, full_text)

    # Extraer roles canónicos desde capítulos empíricos (MÉTODOS, RESULTADOS, …).
    from savt.section_resolver import build_enriched_section_map

    empirical = full_text[boundaries[max(0, len(boundaries) - 3)][1] :]
    enriched, enriched_meta = build_enriched_section_map(empirical)
    for role, text in enriched.items():
        if role in {"presentacion"} and count_words(text) > count_words(empirical) * 0.4:
            continue
        if count_words(text) < 60:
            continue
        if role not in section_map or count_words(text) > count_words(section_map.get(role, "")):
            section_map[role] = text
            section_meta[role] = enriched_meta.get(role) or {
                "detected_titles": [role],
                "from_empirical_chapters": True,
            }

    # Objetivos / justificación suelen estar en CAPÍTULO III
    obj_chunk = ""
    for num, pos, title in boundaries:
        end = next((p for n, p, t in boundaries if p > pos), len(full_text))
        piece = full_text[pos:end]
        if re.search(r"(?i)objetivo\s+general|objetivos\s+espec|justificaci", piece):
            obj_chunk = piece
            break
    if obj_chunk and count_words(obj_chunk) >= 40:
        section_map["objetivos"] = obj_chunk
        section_meta["objetivos"] = {"detected_titles": ["Objetivos / justificación / hipótesis"]}

    # Tabla principal: capítulos (jerarquía real). Hijos van en structure_tree.
    display_sections = flatten_tree_for_display(tree, include_children=False)

    return {
        "body": full_text,
        "bibliography_text": "",
        "section_map": section_map,
        "section_meta": section_meta,
        "index_entries": [],
        "index_sections": display_sections,
        "structure_source": "capitulos",
        "structure_tree": tree,
        "thesis_type": "compendio",
    }


def partition_from_index(
    full_text: str,
    *,
    page_offsets: list[int] | None = None,
    page_count: int | None = None,
) -> dict | None:
    """
    Devuelve body, bibliografía y apartados si el índice es usable.
    None si no hay índice fiable.
    """
    entries = parse_index_entries(full_text)
    top = top_level_index_entries(entries)
    bib_entry = bibliography_index_entry(entries)
    if len(top) < 2 and bib_entry is None:
        return None

    offsets = page_offsets or []
    text_len = len(full_text)
    all_for_locate = top + ([bib_entry] if bib_entry else [])

    if _use_heading_locator(all_for_locate):
        located = _boundaries_from_headings(full_text, all_for_locate)
        if len(located) < 2:
            return None
        bib_start = text_len
        if bib_entry:
            for pos, entry in located:
                if entry.is_bibliography:
                    bib_start = pos
                    break
        boundaries: list[tuple[int, str, str, IndexEntry]] = []
        used_roles: set[str] = set()
        for pos, entry in located:
            if entry.is_bibliography:
                continue
            role = _role_for_entry(entry, used_roles)
            boundaries.append((pos, role, entry.title, entry))
    else:
        boundaries = []
        used_roles: set[str] = set()
        bib_start = text_len
        for entry in top:
            pos = char_offset_for_page(entry.page, offsets, text_len)
            role = _role_for_entry(entry, used_roles)
            boundaries.append((pos, role, entry.title, entry))
        if bib_entry:
            bib_start = char_offset_for_page(bib_entry.page, offsets, text_len)
        boundaries.sort(key=lambda item: item[0])

    section_map: dict[str, str] = {}
    section_meta: dict[str, dict] = {}
    index_sections: list[dict] = []

    for idx, (pos, role, title, entry) in enumerate(boundaries):
        if bib_entry and pos >= bib_start:
            break
        next_pos = (
            boundaries[idx + 1][0]
            if idx + 1 < len(boundaries)
            else bib_start
        )
        chunk = full_text[pos:next_pos].strip()
        if count_words(chunk) < 30:
            continue
        base_role = role.split("_")[0]
        page_display = entry.page_label or str(entry.page)
        if base_role in section_map:
            section_map[base_role] = f"{section_map[base_role]}\n\n{chunk}"
            section_meta[base_role]["detected_titles"].append(title)
        else:
            section_map[base_role] = chunk
            section_meta[base_role] = {
                "detected_titles": [title],
                "index_page": entry.page,
                "index_page_label": page_display,
            }
        index_sections.append(
            {
                "role": base_role,
                "title": title,
                "page": page_display,
                "words": count_words(chunk),
            }
        )

    body_end = bib_start if bib_entry else text_len
    body = full_text[:body_end].strip()
    bib_text = full_text[bib_start:].strip() if bib_entry else ""

    total_body_words = count_words(body)
    covered = 0
    for idx, item in enumerate(index_sections):
        if idx == len(index_sections) - 1:
            item["words"] = max(0, total_body_words - covered)
        covered += item["words"]
        pct = round(item["words"] * 100 / max(total_body_words, 1), 1)
        item["percent"] = pct
        item["percent_label"] = f"{pct:.1f}%"

    return {
        "body": body,
        "bibliography_text": bib_text,
        "section_map": section_map,
        "section_meta": section_meta,
        "index_entries": entries,
        "index_sections": index_sections,
        "structure_source": "index",
    }
