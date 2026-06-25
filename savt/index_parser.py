"""Extracción de apartados principales (1., 2., 3., …) desde el índice del documento."""

from __future__ import annotations

import re
from dataclasses import dataclass

from savt.section_resolver import classify_heading

CONTENT_INDEX_START = re.compile(
    r"(?i)índice\s+de\s+contenido|tabla\s+de\s+contenido",
)
CONTENT_INDEX_END = re.compile(
    r"(?i)índice\s+de\s+figuras|índice\s+de\s+tablas|índice\s+de\s+gráficas",
)
INDEX_HEADING = re.compile(
    r"(?im)^\s*ÍNDICE\s*$|^\s*INDICE\s*$|^\s*TABLA DE CONTENIDO\s*$",
)
_PAGE_IN_PARENS = r"(?:pag\.?|pág\.?|p\.)\s*(\d+)"
INDEX_LINE_PAREN = re.compile(
    rf"(?m)^\s*(\d{{1,2}})(?:\.(?![0-9])|\s+)\s*(.+?)\s*\({_PAGE_IN_PARENS}\s*\)",
    re.IGNORECASE,
)
# Apartado principal: «2. ESTADO DEL ARTE … XXIII» (no 2.1. subapartados).
TOP_LEVEL_LINE = re.compile(
    r"(?m)^\s*(\d{1,2})\.(?!\d)\s*(.+?)\s*(?:[.\u2026…]{2,})\s*([IVXLCDM]+|\d{1,4})\s*$",
    re.IGNORECASE,
)
BIBLIOGRAPHY_TITLE = re.compile(r"(?i)bibliograf|referencias\s+bibliogr|referencias\s*$")
_ROMAN = re.compile(r"^[IVXLCDM]+$", re.I)
_INDEX_ANCHOR = re.compile(
    r"(?i)\b(?:"
    r"índice(?:\s+de\s+(?:contenido|capítulos|general|tablas|figuras|gráficas))?"
    r"|tabla\s+de\s+contenido"
    r"|contenido\s+general"
    r"|sumario"
    r")\b",
)
_INDEX_KEYWORD_SIGNALS: tuple[tuple[str, int], ...] = (
    (r"índice\s+de\s+contenido", 18),
    (r"índice\s+de\s+capítulos", 18),
    (r"tabla\s+de\s+contenido", 16),
    (r"índice\s+general", 14),
    (r"contenido\s+general", 12),
    (r"(?m)^\s*índice\s*$", 10),
    (r"\bsumario\b", 12),
    (r"\bcontenido\b", 6),
)
_MIN_BLOCK_SCORE = 8
_MIN_TOP_LEVEL_SECTIONS = 5
_ORDINAL_WORDS: dict[str, str] = {
    "primero": "1",
    "primera": "1",
    "segundo": "2",
    "segunda": "2",
    "tercero": "3",
    "tercera": "3",
    "cuarto": "4",
    "cuarta": "4",
    "quinto": "5",
    "quinta": "5",
    "sexto": "6",
    "sexta": "6",
    "septimo": "7",
    "séptimo": "7",
    "septima": "7",
    "séptima": "7",
    "octavo": "8",
    "octava": "8",
    "noveno": "9",
    "novena": "9",
    "decimo": "10",
    "décimo": "10",
    "decima": "10",
    "décima": "10",
}
_ORDINAL_WORD_PATTERN = "|".join(re.escape(word) for word in sorted(_ORDINAL_WORDS, key=len, reverse=True))

_INDEX_BLOCK_DIAGNOSTIC: dict | None = None
_INDEX_PARSE_DIAGNOSTIC: dict | None = None


@dataclass(frozen=True)
class IndexEntry:
    number: str
    title: str
    page: int
    role: str | None = None
    page_label: str = ""
    page_is_roman: bool = False

    @property
    def is_bibliography(self) -> bool:
        return bool(BIBLIOGRAPHY_TITLE.search(self.title))


def roman_to_int(value: str) -> int:
    value = value.upper().strip()
    if not value or not _ROMAN.match(value):
        return 0
    numerals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(value):
        current = numerals.get(ch, 0)
        if current < prev:
            total -= current
        else:
            total += current
        prev = current
    return total


def _normalize_section_number(raw: str) -> str | None:
    """Convierte 1, 1-, I, A, primero, etc. al formato interno «1», «2», …"""
    token = raw.strip().rstrip(".-:)")
    if not token:
        return None
    lower = token.lower()
    if lower in _ORDINAL_WORDS:
        return _ORDINAL_WORDS[lower]
    if token.isdigit():
        return str(int(token))
    if _ROMAN.match(token):
        value = roman_to_int(token)
        return str(value) if value > 0 else None
    if re.fullmatch(r"[A-Z]", token, re.IGNORECASE):
        return str(ord(token.upper()) - ord("A") + 1)
    return None


def get_index_parse_diagnostic() -> dict | None:
    """Última decisión entre parser estricto y tolerante."""
    return _INDEX_PARSE_DIAGNOSTIC


def _parse_page_token(token: str) -> tuple[int, str, bool]:
    token = token.strip()
    if _ROMAN.match(token):
        return roman_to_int(token), token.upper(), True
    if token.isdigit():
        return int(token), token, False
    return 0, token, False


def _fix_orphan_index_titles(block: str) -> str:
    """Reasigna número cuando el PDF parte «2.» y el título en la línea siguiente."""
    lines = block.splitlines()
    result: list[str] = []
    pending_number: str | None = None
    for line in lines:
        stripped = line.strip()
        only_num = re.match(r"^(\d{1,2})\.$", stripped)
        if only_num:
            pending_number = only_num.group(1)
            continue
        if pending_number and not re.match(r"^\d", stripped):
            if re.search(r"(?:[.\u2026…]{2,})\s*[IVXLCDM]+\s*$", stripped, re.I):
                result.append(f"{pending_number}. {stripped}")
                pending_number = None
                continue
        pending_number = None
        result.append(line)
    return "\n".join(result)


def _normalize_index_lines(block: str) -> str:
    """Une líneas partidas por el PDF: «3.» en una línea y el título en la siguiente."""
    lines = block.splitlines()
    merged: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if re.match(r"^\d{1,2}\.$", line) and idx + 1 < len(lines):
            nxt = lines[idx + 1].strip()
            if not re.match(r"^\d{1,2}\.$", nxt):
                merged.append(f"{line} {nxt}")
                idx += 2
                continue
        merged.append(line)
        idx += 1
    return "\n".join(merged)


def get_index_block_diagnostic() -> dict | None:
    """Último resultado del modo diagnóstico de `_index_block(diagnose=True)`."""
    return _INDEX_BLOCK_DIAGNOSTIC


def _sequence_coherence_score(numbers: list[int]) -> int:
    """Premia 1,2,3… o subsecuencias crecientes sin saltos grandes."""
    if not numbers:
        return 0
    if numbers[0] == 1:
        score = 8
    elif numbers[0] <= 3:
        score = 4
    else:
        score = 0
    ascending = 0
    for prev, current in zip(numbers, numbers[1:]):
        if current == prev + 1:
            ascending += 3
        elif current > prev:
            ascending += 1
        else:
            ascending -= 2
    return max(0, min(score + ascending, 25))


def _score_index_chunk(raw_chunk: str, normalized: str, *, anchor: str = "") -> tuple[int, dict[str, int]]:
    """Puntúa un bloque candidato según señales estructurales del índice."""
    breakdown: dict[str, int] = {}
    head_sample = raw_chunk[:1200]
    anchor_lower = anchor.lower()

    if re.search(r"(?i)(?:contenido|capítulos)", anchor_lower):
        breakdown["anchor_content_bonus"] = 22
    elif re.search(r"(?i)sumario", anchor_lower):
        breakdown["anchor_sumario_bonus"] = 16

    keyword_total = 0
    for pattern, points in _INDEX_KEYWORD_SIGNALS:
        if re.search(pattern, head_sample, re.IGNORECASE):
            breakdown[f"keyword:{pattern[:28]}"] = points
            keyword_total += points
    breakdown["keywords_total"] = keyword_total

    numbered_lines = len(re.findall(r"(?m)^\s*\d{1,2}\.(?!\d)", normalized))
    breakdown["numbered_lines"] = min(numbered_lines * 3, 45)

    top_level_hits = len(TOP_LEVEL_LINE.findall(normalized))
    breakdown["top_level_lines"] = min(top_level_hits * 4, 40)

    paren_pages = len(re.findall(rf"\({_PAGE_IN_PARENS}\s*\)", normalized, re.IGNORECASE))
    breakdown["paren_pages"] = min(paren_pages * 2, 30)

    roman_tail = len(
        re.findall(r"(?:[.\u2026…]{2,}|\s{2,})\s*[IVXLCDM]{1,8}\s*$", normalized, re.IGNORECASE | re.MULTILINE)
    )
    arabic_tail = len(re.findall(r"\.{2,}\s*\d{1,4}\s*$", normalized, re.MULTILINE))
    breakdown["roman_page_tails"] = min(roman_tail * 2, 25)
    breakdown["arabic_page_tails"] = min(arabic_tail * 2, 20)

    numbers = [
        int(match.group(1))
        for match in re.finditer(r"(?m)^\s*(\d{1,2})\.(?!\d)", normalized)
    ]
    breakdown["numbering_sequence"] = _sequence_coherence_score(numbers)

    entry_count = numbered_lines + top_level_hits + paren_pages
    density = entry_count / max(len(normalized), 1) * 1000
    breakdown["entry_density"] = min(int(density * 2), 20)

    length = len(normalized)
    if 400 <= length <= 18_000:
        breakdown["block_length"] = 10
    elif 200 <= length < 400:
        breakdown["block_length"] = 3
    elif length > 18_000:
        breakdown["block_length"] = 4
    else:
        breakdown["block_length"] = -8

    if re.search(r"(?i)índice\s+de\s+figuras", head_sample):
        breakdown["figures_index_penalty"] = -40
    if re.search(r"(?i)índice\s+de\s+tablas", head_sample):
        breakdown["tables_index_penalty"] = -35
    if re.search(r"(?i)índice\s+de\s+(?:figuras|tablas|gráficas)", anchor_lower):
        breakdown["secondary_anchor_penalty"] = -50

    figura_lines = len(re.findall(r"(?m)^Figura\s+\d", normalized, re.IGNORECASE))
    if figura_lines:
        breakdown["figura_entry_penalty"] = -min(figura_lines * 4, 80)

    total = sum(breakdown.values())
    return total, breakdown


def _extract_index_lines_fallback(chunk: str) -> str:
    """Filtra líneas con señales de entrada de índice (formato «(pag. N)» o puntos+romano)."""
    lines = chunk.splitlines()
    kept: list[str] = []
    empty_run = 0
    for line in lines:
        if re.search(rf"\({_PAGE_IN_PARENS}\s*\)", line, re.I):
            kept.append(line)
            empty_run = 0
            continue
        if TOP_LEVEL_LINE.search(line) or re.search(r"\.{2,}\s*[IVXLCDM]+\s*$", line, re.I):
            kept.append(line)
            empty_run = 0
            continue
        if not line.strip():
            empty_run += 1
            if empty_run > 4 and kept:
                break
            continue
        if kept and not re.match(r"^\s*\d", line):
            empty_run += 1
            if empty_run > 2:
                break
        kept.append(line)
    return _normalize_index_lines("\n".join(kept))


def _candidate_chunks(head: str) -> list[dict]:
    """Genera bloques candidatos sin depender de una sola expresión exacta."""
    candidates: list[dict] = []
    seen_keys: set[tuple[int, str]] = set()

    def add_candidate(start: int, raw: str, anchor: str, source: str) -> None:
        if not raw.strip():
            return
        key = (start, anchor.strip().lower()[:48])
        if key in seen_keys:
            return
        seen_keys.add(key)
        candidates.append(
            {"start": start, "raw": raw, "anchor": anchor, "source": source}
        )

    for match in _INDEX_ANCHOR.finditer(head):
        tail = head[match.end() : match.end() + 22_000]
        end_match = CONTENT_INDEX_END.search(tail)
        chunk = tail[: end_match.start()] if end_match else tail[:18_000]
        add_candidate(match.start(), chunk, match.group(0), "anchor_keyword")

    for match in INDEX_HEADING.finditer(head):
        chunk = head[match.end() : match.end() + 12_000]
        add_candidate(match.start(), chunk, match.group(0).strip(), "index_heading")

    first_pag = re.search(rf"\({_PAGE_IN_PARENS}\s*\)", head, re.IGNORECASE)
    if first_pag and first_pag.start() <= 8_000:
        chunk = head[max(0, first_pag.start() - 4_000) : first_pag.start() + 8_000]
        add_candidate(max(0, first_pag.start() - 4_000), chunk, "(pag. N)", "pag_cluster")

    # Ventanas alrededor de agrupaciones de líneas numeradas de primer nivel.
    for match in re.finditer(r"(?m)^\s*\d{1,2}\.(?!\d)", head):
        if match.start() > 25_000:
            break
        start = max(0, match.start() - 800)
        chunk = head[start : start + 14_000]
        add_candidate(start, chunk, f"numbered@{match.start()}", "numbered_window")

    return candidates


def _index_block(full_text: str, *, diagnose: bool = False) -> str:
    """Recorta el bloque de índice de contenido (no figuras/tablas) por puntuación."""
    global _INDEX_BLOCK_DIAGNOSTIC

    head = full_text[: min(len(full_text), 45_000)]
    raw_candidates = _candidate_chunks(head)

    scored: list[dict] = []
    for item in raw_candidates:
        variants = {
            "normalized": _normalize_index_lines(item["raw"]),
            "fallback_lines": _extract_index_lines_fallback(item["raw"]),
        }
        best_for_item: dict | None = None
        for variant_name, normalized in variants.items():
            if not normalized.strip():
                continue
            total, breakdown = _score_index_chunk(item["raw"], normalized, anchor=item["anchor"])
            record = {
                **item,
                "variant": variant_name,
                "normalized_preview_len": len(normalized),
                "score": total,
                "breakdown": breakdown,
            }
            if best_for_item is None or record["score"] > best_for_item["score"]:
                best_for_item = record
        if best_for_item:
            scored.append(best_for_item)

    scored.sort(key=lambda row: row["score"], reverse=True)
    winner = scored[0] if scored and scored[0]["score"] >= _MIN_BLOCK_SCORE else None

    if diagnose:
        _INDEX_BLOCK_DIAGNOSTIC = {
            "min_score": _MIN_BLOCK_SCORE,
            "candidates": scored,
            "selected": winner,
        }
    else:
        _INDEX_BLOCK_DIAGNOSTIC = None

    if not winner:
        return ""

    winner_raw = winner["raw"]
    if winner["variant"] == "fallback_lines":
        prepared = _extract_index_lines_fallback(winner_raw)
    else:
        prepared = _normalize_index_lines(winner_raw)

    return _strip_subsections(_fix_orphan_index_titles(prepared))


def _strip_subsections(block: str) -> str:
    top_lines: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d{1,2}\.\d", stripped):
            continue
        if re.match(r"^Figura\s+\d", stripped, re.I):
            break
        top_lines.append(stripped)
    return "\n".join(top_lines)


def _entry_from_match(number: str, title: str, page_token: str) -> IndexEntry | None:
    normalized_number = _normalize_section_number(number)
    if not normalized_number:
        return None
    title = re.sub(r"\s+", " ", title).strip().rstrip(".")
    if len(title) < 3:
        return None
    page, label, is_roman = _parse_page_token(page_token)
    if page <= 0 and not is_roman:
        return None
    if page <= 0:
        page = 1
    role = classify_heading(title)
    return IndexEntry(
        number=normalized_number,
        title=title,
        page=page,
        role=role,
        page_label=label,
        page_is_roman=is_roman,
    )


def _page_token_from_match(match: re.Match[str]) -> str:
    for idx in range(3, (match.lastindex or 0) + 1):
        token = (match.group(idx) or "").strip()
        if token:
            return token
    if (match.lastindex or 0) >= 2:
        token = (match.group(2) or "").strip()
        if token.isdigit() or (len(token) <= 8 and _ROMAN.match(token)):
            return token
    return ""


def _index_fallback_patterns(*, tolerant: bool) -> tuple[re.Pattern[str], ...]:
    _dots = r"[.\u2026…]{2,}"
    _page = r"([IVXLCDM]+|\d{1,4})"
    _page_suffix = rf"(?:\s*(?:{_dots}\s*)?{_page})?"
    _loose_page_suffix = rf"(?:\s*(?:{_dots}\s*)?{_page}|\s+{_page})?"
    _flags = re.IGNORECASE
    patterns: list[re.Pattern[str]] = [
        re.compile(rf"^(\d{{1,2}})\s+(.+?)\s*(?:{_dots}\s*)?{_page}\s*$", _flags),
        re.compile(rf"^(\d{{1,2}})(?:\.-|-|[\):]|\s*:\s*)\s*(.+?){_page_suffix}\s*$", _flags),
        re.compile(rf"^(\d{{1,2}})\.(?!\d)\s*(.+?){_page_suffix}\s*$", _flags),
        re.compile(rf"^cap[ií]tulo\s+(\d{{1,2}})\.?\s*(.+?){_page_suffix}\s*$", _flags),
        re.compile(rf"^cap[ií]tulo\s+(\d{{1,2}})\s+(.+?){_page_suffix}\s*$", _flags),
        re.compile(rf"^cap[ií]tulo\s+([IVXLCDM]+)\.?\s*(.+?){_page_suffix}\s*$", _flags),
        re.compile(
            rf"^cap[ií]tulo\s+({_ORDINAL_WORD_PATTERN})\.?\s*(.+?){_page_suffix}\s*$",
            _flags,
        ),
        re.compile(rf"^([IVXLCDM]{{2,8}})\s+([A-ZÁÉÍÓÚÑÜ].+?){_page_suffix}\s*$", _flags),
        re.compile(rf"^I\s+([A-ZÁÉÍÓÚÑÜ][^\d].+?){_page_suffix}\s*$", _flags),
        re.compile(rf"^([A-Z])\s+([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ\s]{{3,}}.+?){_page_suffix}\s*$", _flags),
        re.compile(
            rf"^(\d{{1,2}})(?:\.(?![0-9])|\s+)\s*(.+?)\s*\((?:pag\.?|pág\.?|p\.)\s*(\d+)\s*\)",
            _flags,
        ),
    ]
    if tolerant:
        patterns.extend(
            [
                re.compile(rf"^(\d{{1,2}})\s+(.+?){_loose_page_suffix}\s*$", _flags),
                re.compile(rf"^(\d{{1,2}})\.(?!\d)\s*(.+?){_loose_page_suffix}\s*$", _flags),
                re.compile(rf"^cap[ií]tulo\s+(\d{{1,2}})\.?\s*(.+?){_loose_page_suffix}\s*$", _flags),
                re.compile(rf"^([IVXLCDM]{{2,8}})\s+([A-ZÁÉÍÓÚÑÜ].+?){_loose_page_suffix}\s*$", _flags),
                re.compile(rf"^I\s+([A-ZÁÉÍÓÚÑÜ][^\d].+?){_loose_page_suffix}\s*$", _flags),
            ]
        )
    return tuple(patterns)


_INDEX_SKIP_LINE = re.compile(
    r"(?i)^(?:tabla|figura|gráfico|anexo\s+[ivxlcdm\d]+)\s+\d|"
    r"^índice\s+de\s+(?:tablas|figuras|gráficos)",
)


def _prepare_tolerant_block(block: str) -> str:
    """Normaliza espacios, tabulaciones y títulos partidos para el modo tolerante."""
    page_token = r"(?:[IVXLCDM]+|\d{1,4})"
    block = block.replace("\t", " ")
    lines = [re.sub(r" {2,}", " ", line.strip()) for line in block.splitlines()]
    merged: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if not line:
            idx += 1
            continue

        if re.fullmatch(r"(?i)cap[ií]tulo", line) and idx + 1 < len(lines):
            merged.append(f"CAPÍTULO {lines[idx + 1]}")
            idx += 2
            continue

        only_number = re.fullmatch(r"(\d{1,2})[-.]?", line)
        if only_number and idx + 1 < len(lines):
            title_line = lines[idx + 1]
            if not re.match(r"^\d{1,2}[-.]", title_line):
                combined = f"{only_number.group(1)}. {title_line}"
                if idx + 2 < len(lines):
                    page_candidate = lines[idx + 2].strip()
                    if re.fullmatch(page_token, page_candidate, re.I):
                        combined = f"{combined} {page_candidate}"
                        idx += 1
                merged.append(combined)
                idx += 2
                continue

        if (
            idx + 1 < len(lines)
            and not re.search(r"(?:[.\u2026…]{2,}|\s)\d{1,4}\s*$", line)
            and re.fullmatch(page_token, lines[idx + 1].strip(), re.I)
            and len(line) > 8
        ):
            merged.append(f"{line} {lines[idx + 1].strip()}")
            idx += 2
            continue

        merged.append(line)
        idx += 1

    return _normalize_index_lines("\n".join(merged))


def _finalize_index_entries(entries: list[IndexEntry]) -> list[IndexEntry]:
    entries.sort(key=lambda item: (int(item.number) if item.number.isdigit() else 99, item.page))

    if entries and entries[0].number != "1" and entries[0].number.isdigit():
        if int(entries[0].number) >= 2:
            entries.insert(
                0,
                IndexEntry(
                    number="1",
                    title="INTRODUCCIÓN",
                    page=1,
                    role="introduccion",
                    page_label="I",
                    page_is_roman=True,
                ),
            )

    return _dedupe_by_number(entries)


def _entries_coherence_score(entries: list[IndexEntry]) -> int:
    top = top_level_index_entries(entries)
    if not top:
        return 0

    score = len(top) * 12
    numbers = [int(entry.number) for entry in top if entry.number.isdigit()]
    score += _sequence_coherence_score(numbers)

    pages = [entry.page for entry in top]
    if len(pages) > 1:
        ascending = sum(1 for prev, current in zip(pages, pages[1:]) if current >= prev)
        score += ascending * 3
        if pages == sorted(pages):
            score += 10

    score += len(set(numbers)) * 4
    score -= sum(1 for entry in top if len(entry.title) < 5) * 6
    score += sum(1 for entry in top if entry.page_label) * 2
    return score


def _parse_index_entries_from_block(block: str, *, tolerant: bool = False) -> list[IndexEntry]:
    if tolerant:
        block = _prepare_tolerant_block(block)

    entries: list[IndexEntry] = []
    seen: set[tuple[str, str]] = set()
    matched_line_nos: set[int] = set()

    def add_entry(
        number: str,
        title: str,
        page_token: str,
        *,
        line_no: int | None = None,
    ) -> bool:
        normalized_number = _normalize_section_number(number)
        if not normalized_number:
            return False
        title = re.sub(r"\s+", " ", title).strip().rstrip(".")
        if len(title) < 3:
            return False
        key = (normalized_number, title[:40].upper())
        if key in seen:
            return False
        if page_token:
            entry = _entry_from_match(normalized_number, title, page_token)
        else:
            order = int(normalized_number)
            entry = IndexEntry(
                number=normalized_number,
                title=title,
                page=order,
                role=classify_heading(title),
                page_label="",
                page_is_roman=False,
            )
        if not entry:
            return False
        seen.add(key)
        entries.append(entry)
        if line_no is not None:
            matched_line_nos.add(line_no)
        return True

    for pattern in (INDEX_LINE_PAREN, TOP_LEVEL_LINE):
        for match in pattern.finditer(block):
            line_no = block[: match.start()].count("\n")
            add_entry(match.group(1), match.group(2), match.group(3), line_no=line_no)

    fallback_patterns = _index_fallback_patterns(tolerant=tolerant)
    for line_no, line in enumerate(block.splitlines()):
        if line_no in matched_line_nos:
            continue
        stripped = line.strip()
        if len(stripped) < 5 or _INDEX_SKIP_LINE.search(stripped):
            continue
        if re.match(r"^\d{1,2}\.\d", stripped):
            continue

        for pattern in fallback_patterns:
            match = pattern.search(stripped)
            if not match:
                continue
            first_group = match.group(1).strip()
            if _normalize_section_number(first_group) and (match.lastindex or 0) >= 2:
                raw_number = first_group
                title = match.group(2)
            else:
                raw_number = "I"
                title = match.group(1)
            page_token = _page_token_from_match(match)
            if add_entry(raw_number, title, page_token, line_no=line_no):
                break

    return _finalize_index_entries(entries)


def parse_index_entries(full_text: str) -> list[IndexEntry]:
    """Apartados del índice: número, título y página (arábiga o romana)."""
    global _INDEX_PARSE_DIAGNOSTIC

    block = _index_block(full_text)
    if not block:
        _INDEX_PARSE_DIAGNOSTIC = None
        return []

    strict_entries = _parse_index_entries_from_block(block, tolerant=False)
    strict_top = len(top_level_index_entries(strict_entries))

    if strict_top >= _MIN_TOP_LEVEL_SECTIONS:
        _INDEX_PARSE_DIAGNOSTIC = {
            "mode": "strict",
            "strict_top_level": strict_top,
            "tolerant_top_level": None,
            "strict_coherence": _entries_coherence_score(strict_entries),
            "tolerant_coherence": None,
        }
        return strict_entries

    tolerant_entries = _parse_index_entries_from_block(block, tolerant=True)
    strict_score = _entries_coherence_score(strict_entries)
    tolerant_score = _entries_coherence_score(tolerant_entries)
    selected = tolerant_entries if tolerant_score > strict_score else strict_entries

    _INDEX_PARSE_DIAGNOSTIC = {
        "mode": "tolerant" if tolerant_score > strict_score else "strict",
        "strict_top_level": strict_top,
        "tolerant_top_level": len(top_level_index_entries(tolerant_entries)),
        "strict_coherence": strict_score,
        "tolerant_coherence": tolerant_score,
    }
    return selected


def _entry_index_priority(entry: IndexEntry) -> tuple[int, int, int, int]:
    synthetic_page = entry.page == int(entry.number) if entry.number.isdigit() else False
    return (
        1 if entry.page_label else 0,
        0 if synthetic_page and not entry.page_label else 1,
        sum(1 for char in entry.title if char.isupper()),
        len(entry.title),
    )


def _dedupe_by_number(entries: list[IndexEntry]) -> list[IndexEntry]:
    best_by_number: dict[str, IndexEntry] = {}
    for entry in entries:
        current = best_by_number.get(entry.number)
        if current is None or _entry_index_priority(entry) > _entry_index_priority(current):
            best_by_number[entry.number] = entry
    ordered_numbers = sorted(
        best_by_number,
        key=lambda value: int(value) if value.isdigit() else 99,
    )
    return [best_by_number[number] for number in ordered_numbers]


def top_level_index_entries(entries: list[IndexEntry]) -> list[IndexEntry]:
    """Solo apartados de primer nivel (1, 2, 3…) excluyendo bibliografía y anexos."""
    top: list[IndexEntry] = []
    for entry in entries:
        if not entry.number.isdigit():
            continue
        if entry.is_bibliography:
            continue
        if re.search(r"(?i)^anexo", entry.title):
            continue
        top.append(entry)
    return top


def bibliography_index_entry(entries: list[IndexEntry]) -> IndexEntry | None:
    for entry in entries:
        if entry.is_bibliography:
            return entry
    return None
