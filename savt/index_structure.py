"""Partición del documento según el índice y conteo de palabras por apartado."""

from __future__ import annotations

from savt.index_parser import (
    IndexEntry,
    bibliography_index_entry,
    parse_index_entries,
    top_level_index_entries,
)
from savt.section_resolver import classify_heading
from savt.word_stats import count_words


def page_char_offsets(page_texts: list[str]) -> list[int]:
    """Posición de inicio de cada página en el texto concatenado."""
    offsets: list[int] = []
    pos = 0
    for idx, text in enumerate(page_texts):
        offsets.append(pos)
        pos += len(text)
        if idx < len(page_texts) - 1:
            pos += 1  # salto de línea entre páginas
    return offsets


def char_offset_for_page(page: int, offsets: list[int], text_len: int) -> int:
    if page <= 1:
        return 0
    if offsets and page <= len(offsets):
        return min(offsets[page - 1], text_len)
    if offsets:
        # Página fuera de rango: interpolar.
        last_page = len(offsets)
        ratio = (page - 1) / max(last_page - 1, 1)
        return min(int(ratio * text_len), text_len)
    return min(int((page - 1) / 300 * text_len), text_len)


def _role_for_entry(entry: IndexEntry, used_roles: set[str]) -> str:
    role = entry.role or classify_heading(entry.title) or "otros"
    if role in used_roles and role != "otros":
        role = f"{role}_{entry.number}"
    used_roles.add(role.split("_")[0])
    return role


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

    boundaries: list[tuple[int, str, str, IndexEntry]] = []
    used_roles: set[str] = set()
    for entry in top:
        pos = char_offset_for_page(entry.page, offsets, text_len)
        role = _role_for_entry(entry, used_roles)
        boundaries.append((pos, role, entry.title, entry))

    bib_start = text_len
    if bib_entry:
        bib_start = char_offset_for_page(bib_entry.page, offsets, text_len)

    boundaries.sort(key=lambda item: item[0])
    section_map: dict[str, str] = {}
    section_meta: dict[str, dict] = {}
    index_sections: list[dict] = []

    for idx, (pos, role, title, entry) in enumerate(boundaries):
        if bib_entry and pos >= bib_start:
            break
        next_pos = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else bib_start
        chunk = full_text[pos:next_pos].strip()
        if count_words(chunk) < 30:
            continue
        base_role = role.split("_")[0]
        if base_role in section_map:
            section_map[base_role] = f"{section_map[base_role]}\n\n{chunk}"
            section_meta[base_role]["detected_titles"].append(title)
        else:
            section_map[base_role] = chunk
            section_meta[base_role] = {"detected_titles": [title], "index_page": entry.page}
        index_sections.append(
            {
                "role": base_role,
                "title": title,
                "page": entry.page,
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
