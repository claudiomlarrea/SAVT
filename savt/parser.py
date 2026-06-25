from __future__ import annotations

import io
import re
import zipfile
from typing import BinaryIO
from xml.etree import ElementTree as ET

from savt.models import ReferenceEntry

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

CHAPTER_PATTERN = re.compile(
    r"^(CAPÍTULO|CAPITULO)\s+([IVXLC]+|\d+)\.\s*(.+)$",
    re.IGNORECASE,
)
SECTION_PATTERN = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$")
NUMERIC_CITATION_PATTERN = re.compile(r"\((\d+(?:\s*[,\s\-–]\s*\d+)*)\)")
NUMBERED_BIB_ENTRY_START = re.compile(
    r"(?m)^(\d+)\.\s+([A-Za-zÁÉÍÓÚáéíóúñ\"(].*)"
)
STATISTICAL_CONTEXT = re.compile(
    r"(?i)(?:\bp\s*[<>=]|\bvalor\s+p\b|\bic\s*\(|\bnivel\s+de\s+significancia|\balpha\b|\bα\b|"
    r"significativo\s*\(|no\s+significativo)"
)
BIB_HEADING = re.compile(
    r"(?m)^\s*(?:[A-ZÁÉÍÓÚÑ]{2,12}\s+)?BIBLIOGRAF[IÍÁ][A-Z]*\s*$",
    re.IGNORECASE,
)
BIB_HEADING_NUMBERED = re.compile(
    r"(?m)^\s*\d+\.?\s*BIBLIOGRAF[IÍÁ][A-Z]*\s*(?:\n|$)",
    re.IGNORECASE,
)
BIB_HEADING_LINE = re.compile(
    r"(?m)^\s*BIBLIOGRAF[IÍÁ][A-Z]*\s*\n",
    re.IGNORECASE,
)
REFERENCIAS_HEADING = re.compile(r"(?m)^\s*REFERENCIAS\s*$", re.IGNORECASE)
BIB_SUBSECTION = re.compile(
    r"(?i)LEGISLATIVA|JURISPRUDENC|NORMATIVA|CONSULTADA|BIBLIOGRAF[IÍ]AS\s+WEB|FUENTES\s+CONSULTADAS"
)
APA_BIB_ENTRY_HINT = re.compile(
    r"(?m)^[A-ZÁÉÍÓÚÑ\"(][^\n]{4,80},\s*[A-ZÁÉÍÓÚa-záéíóúñ]"
)
NUMBERED_BIB_ENTRY_HINT = re.compile(r"(?m)^\d+\.\s+[A-Za-zÁÉÍÓÚáéíóúñ\"(]")


def _bibliography_heading_line(full_text: str, pos: int) -> str:
    end = full_text.find("\n", pos)
    if end == -1:
        end = min(pos + 160, len(full_text))
    return full_text[pos:end]


def _is_index_bibliography_line(line: str, pos: int, doc_len: int) -> bool:
    if re.search(r"\(pag\.", line, re.I):
        return pos < doc_len * 0.15
    return bool(re.search(r"\.{3,}\s*\d+\s*$", line))


def _score_bibliography_candidate(full_text: str, pos: int) -> int:
    line = _bibliography_heading_line(full_text, pos)
    if not re.search(r"(?i)BIBLIOGRAF|REFERENCIAS", line[:60]):
        return -100
    if BIB_SUBSECTION.search(line):
        return -100
    if _is_index_bibliography_line(line, pos, len(full_text)):
        return -50

    score = 0
    if re.match(r"(?i)^\s*\d+\.?\s*BIBLIOGRAF", line):
        score += 70
    elif re.match(r"(?i)^\s*BIBLIOGRAF", line):
        score += 55
    elif re.match(r"(?i)^\s*REFERENCIAS\s*$", line):
        score += 50

    relative = pos / max(len(full_text), 1)
    if relative > 0.55:
        score += 30
    elif relative > 0.4:
        score += 15

    following = full_text[pos : pos + 8000]
    apa_entries = len(APA_BIB_ENTRY_HINT.findall(following))
    numbered_entries = len(NUMBERED_BIB_ENTRY_HINT.findall(following))
    score += min(apa_entries + numbered_entries, 35)
    return score


def _bibliography_start_positions(full_text: str) -> list[int]:
    candidates: set[int] = set()
    inline_patterns = [
        r"(?im)^\s*(?:\d+\.?\s*)?BIBLIOGRAF[IÍÁ][A-Z]*\s*(?:\n|$)",
        r"(?im)^\s*REFERENCIAS\s*$",
        r"(?im)\n\n\s*(?:\d+\.?\s*)?BIBLIOGRAF[IÍÁ][A-Z]*\s*(?:\n\s*)?(?=[A-ZÁÉÍÓÚ\"(])",
        r"(?im)\n\n\s*BIBLIOGRAF[IÍÁ][A-Z]*\s*(?:\n\s*)?(?=[A-ZÁÉÍÓÚ\"(])",
        r"(?im)(?:^|\n\n)\s*BIBLIOGRAF[IÍÁ][A-Z]*\s*\n\s*\d+\.\s+[A-Za-zÁÉÍÓÚ\"(]",
    ]
    heading_in_match = re.compile(r"(?i)(?:\d+\.?\s*)?BIBLIOGRAF[IÍÁ][A-Z]*|^REFERENCIAS")
    for pattern in inline_patterns:
        for match in re.finditer(pattern, full_text):
            chunk = match.group(0)
            heading = heading_in_match.search(chunk)
            if heading:
                candidates.add(match.start() + heading.start())

    for pattern in (BIB_HEADING_NUMBERED, BIB_HEADING, BIB_HEADING_LINE, REFERENCIAS_HEADING):
        for match in pattern.finditer(full_text):
            candidates.add(match.start())

    scored = [(pos, _score_bibliography_candidate(full_text, pos)) for pos in candidates]
    scored = [(pos, score) for pos, score in scored if score > 0]
    if not scored:
        return []
    best_score = max(score for _, score in scored)
    return [pos for pos, score in scored if score >= best_score - 5]
RESEARCH_QUESTION = re.compile(
    r"¿[^?]+\?",
    re.MULTILINE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _read_docx_bytes(source: BinaryIO | str) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, str):
        with open(source, "rb") as handle:
            return handle.read()
    source.seek(0)
    return source.read()


def extract_paragraphs_from_docx_xml(source: BinaryIO | str) -> list[str]:
    data = _read_docx_bytes(source)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", WORD_NS):
        texts = [node.text for node in paragraph.findall(".//w:t", WORD_NS) if node.text]
        if not texts:
            continue
        text = _normalize("".join(texts))
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_text_from_docx(source: BinaryIO | str) -> str:
    paragraphs = extract_paragraphs_from_docx_xml(source)
    return "\n\n".join(paragraphs)


def split_body_and_bibliography(full_text: str) -> tuple[str, str]:
    positions = _bibliography_start_positions(full_text)
    if positions:
        best_score = max(_score_bibliography_candidate(full_text, pos) for pos in positions)
        top = [pos for pos in positions if _score_bibliography_candidate(full_text, pos) >= best_score - 2]
        idx = max(top)
        body = full_text[:idx].strip()
        bib = full_text[idx:].strip()
        bib = re.sub(
            r"^(?:\d+\.?\s*)?(?:[A-ZÁÉÍÓÚÑ]{2,12}\s+)?BIBLIOGRAF[IÍÁ][A-Z]*\s*",
            "BIBLIOGRAFÍA\n",
            bib,
            count=1,
            flags=re.IGNORECASE,
        )
        bib = re.sub(r"^REFERENCIAS\s*", "REFERENCIAS\n", bib, flags=re.IGNORECASE)
        return body, bib
    return full_text, ""


def remove_index_duplicate(body: str) -> str:
    """Elimina portada + índice automático, conservando el cuerpo real del documento."""
    markers = [
        "1.1 Presentación del tema",
        "1.1 Presentacion del tema",
    ]
    for marker in markers:
        positions = [match.start() for match in re.finditer(re.escape(marker), body)]
        if len(positions) >= 2:
            return body[positions[1] :].strip()

    content_start = re.search(
        r"CAPÍTULO I\.\s*INTRODUCCIÓN\s*\n+\s*1\.1\s+Presentaci[oó]n del tema\s*\n",
        body,
        re.IGNORECASE,
    )
    if content_start:
        return body[content_start.start() :].strip()
    return body


def _looks_like_bibliography_entry(raw: str) -> bool:
    if len(raw) < 30:
        return False
    body = re.sub(r"^(?:\[\d+\]|\d+\.)\s*", "", raw)
    body = re.sub(r"^\d+\)\s*", "", body)
    if re.match(r"(?i)(?:disponible|available)\b", body):
        return False
    if not re.match(r'[A-ZÁÉÍÓÚa-z"(]', body):
        return False
    if sum(char.isdigit() for char in body) / max(len(body), 1) > 0.35:
        return False
    if re.search(r"\b(19|20)\d{2}\b", raw):
        return True
    if re.search(r"doi|PMID|ISBN|https?://|Journal|Rev\.|vol\.", raw, re.I):
        return True
    if re.search(r"[A-ZÁÉÍÓÚa-z][A-Za-zÁÉÍÓÚáéíóúñ'\-]+,\s+[A-Z]", raw):
        return True
    return len(body) > 80


_NUMBERED_REFERENCE_START_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?m)^(\d{1,3})\.\s+(?=[A-Za-zÁÉÍÓÚáéíóúñ\"'(])"),
    re.compile(r"(?m)^\[(\d{1,3})\]\s+(?=[A-Za-zÁÉÍÓÚáéíóúñ\"'(])"),
    re.compile(r"(?m)^(\d{1,3})\)\s+(?=[A-Za-zÁÉÍÓÚáéíóúñ\"'(])"),
)
_NUMBERED_REFERENCE_NUMBER_ONLY = re.compile(r"(?m)^(\d{1,3})\.\s*$")


def _prepare_multiline_bibliography_text(bib_text: str) -> str:
    """Une números de referencia aislados con el bloque multilínea siguiente."""
    lines = bib_text.splitlines()
    merged: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        number_only = _NUMBERED_REFERENCE_NUMBER_ONLY.match(stripped)
        if number_only and idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if next_line and not _NUMBERED_REFERENCE_NUMBER_ONLY.match(next_line):
                merged.append(f"{number_only.group(1)}. {next_line}")
                idx += 2
                continue
        merged.append(line)
        idx += 1
    return "\n".join(merged)


def _collect_numbered_reference_starts(text: str) -> list[tuple[int, int]]:
    """Devuelve (número, offset) ordenados; una referencia puede ocupar varias líneas."""
    candidates: list[tuple[int, int]] = []
    for pattern in _NUMBERED_REFERENCE_START_PATTERNS:
        for match in pattern.finditer(text):
            number = int(match.group(1))
            if 1 <= number <= 999:
                candidates.append((match.start(), number))

    if not candidates:
        return []

    candidates.sort(key=lambda item: item[0])
    starts: list[tuple[int, int]] = []
    last_pos = -1
    for pos, number in candidates:
        if pos == last_pos:
            continue
        if starts and pos < starts[-1][0] + 8:
            continue
        starts.append((number, pos))
        last_pos = pos
    return starts


def _reference_chunk_to_raw(text: str, start: int, end: int) -> str:
    chunk = text[start:end].strip()
    chunk = re.sub(r"\s*\n\s*", " ", chunk)
    return _normalize(re.sub(r" {2,}", " ", chunk))


def _build_reference_entry(number: int, raw: str) -> ReferenceEntry:
    doi_match = re.search(r"https?://doi\.org/([^\s]+)", raw, re.IGNORECASE)
    if not doi_match:
        doi_match = re.search(r"doi[:.]?\s*(10\.\S+)", raw, re.IGNORECASE)
    pmid_match = re.search(r"PMID:?\s*(\d+)", raw, re.IGNORECASE)
    year_match = re.search(r"\b(19|20)\d{2}\b", raw)
    year = year_match.group(0) if year_match else ""
    if year and not (1900 <= int(year) <= 2030):
        paren_year = re.search(r"\((\d{4}[a-z]?)\)", raw)
        year = paren_year.group(1)[:4] if paren_year else ""
    doi_value = doi_match.group(1).rstrip(".,;") if doi_match else ""
    doi_value = re.sub(r"^https?://doi\.org/", "", doi_value, flags=re.I)
    title = raw.split(". ", 1)[1][:180] if ". " in raw else raw[:180]
    return ReferenceEntry(
        number=number,
        raw=raw,
        title=title,
        doi=doi_value,
        pmid=pmid_match.group(1) if pmid_match else "",
        year=year,
    )


def _parse_numbered_bibliography_blocks(bib_text: str) -> dict[int, ReferenceEntry]:
    """Parser multilínea: cada referencia termina al iniciar la siguiente."""
    if not bib_text:
        return {}

    cleaned = re.sub(
        r"^(?:\s*BIBLIOGRAF[IÍ]A|REFERENCIAS)\s*\n?",
        "",
        bib_text,
        flags=re.IGNORECASE,
    )
    cleaned = _prepare_multiline_bibliography_text(cleaned)
    starts = _collect_numbered_reference_starts(cleaned)
    entries: dict[int, ReferenceEntry] = {}

    for index, (number, start) in enumerate(starts):
        end = starts[index + 1][1] if index + 1 < len(starts) else len(cleaned)
        raw = _reference_chunk_to_raw(cleaned, start, end)
        if not _looks_like_bibliography_entry(raw):
            continue
        if number not in entries or len(raw) > len(entries[number].raw):
            entries[number] = _build_reference_entry(number, raw)

    return entries


def parse_numbered_bibliography(bib_text: str) -> dict[int, ReferenceEntry]:
    return trim_numbered_bibliography_range(_parse_numbered_bibliography_blocks(bib_text))


def trim_numbered_bibliography_range(entries: dict[int, ReferenceEntry]) -> dict[int, ReferenceEntry]:
    """Conserva entradas en el rango 1–N consecutivo (estilo Vancouver)."""
    if not entries:
        return {}
    n = 0
    while (n + 1) in entries:
        n += 1
    if n >= 5:
        return {num: entries[num] for num in range(1, n + 1)}

    nums = sorted(num for num in entries if num >= 1)
    if not nums:
        return {}
    n_cap = nums[-1]
    while len(nums) >= 2 and n_cap - nums[-2] > 50:
        nums = nums[:-1]
        n_cap = nums[-1]
    return {num: entries[num] for num in nums if 1 <= num <= n_cap}


def parse_bibliography_line_by_line(bib_text: str) -> dict[int, ReferenceEntry]:
    """Compatibilidad: delega en el parser multilínea por bloques."""
    return parse_numbered_bibliography(bib_text)


def parse_bibliography(bib_text: str) -> dict[int, ReferenceEntry]:
    return parse_numbered_bibliography(bib_text)


def _is_decimal_notation(chunk: str) -> bool:
    compact = chunk.replace(" ", "")
    return bool(re.fullmatch(r"0,\d{2,3}", compact))


def _is_false_positive_numeric_citation(chunk: str, body: str, start: int) -> bool:
    if _is_decimal_notation(chunk):
        return True
    parts = [part for part in re.split(r"[,\s\-–]+", chunk) if part.isdigit()]
    if not parts:
        return True
    numbers = [int(part) for part in parts]
    if 0 in numbers:
        return True
    if len(numbers) == 1 and 1 <= numbers[0] <= 200:
        return False
    before = body[max(0, start - 80) : start]
    if STATISTICAL_CONTEXT.search(before):
        if len(numbers) == 1 and numbers[0] > 100:
            return True
    return False


def count_numeric_citation_appearances(body: str, max_ref: int = 500) -> int:
    from savt.citations import count_numeric_citation_appearances as _count

    return _count(body, max_ref=max_ref)


def extract_cited_numbers(body: str, max_ref: int = 500) -> set[int]:
    from savt.citations import extract_cited_numbers as _extract

    return _extract(body, max_ref=max_ref)


def _numbered_bibliography_max(bibliography: dict[int, ReferenceEntry]) -> int:
    """Índice máximo plausible de referencias numeradas (excluye PMIDs mal parseados)."""
    valid = [k for k in bibliography if 1 <= k <= 500]
    return max(valid) if valid else 500


def split_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {"general": body}
    current_key = "general"
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines:
            sections[current_key] = "\n".join(current_lines).strip()

    for line in body.splitlines():
        stripped = line.strip()
        chapter = CHAPTER_PATTERN.match(stripped)
        section = SECTION_PATTERN.match(stripped)
        if chapter:
            flush()
            roman = chapter.group(2).upper()
            title = chapter.group(3).strip()
            current_key = f"cap_{roman}_{title[:40]}"
            current_lines = [stripped]
        elif section:
            flush()
            current_key = f"sec_{section.group(1)}"
            current_lines = [stripped]
        else:
            current_lines.append(line)
    flush()
    return sections


def extract_citation_contexts(body: str, max_ref: int = 500) -> list[tuple[int, str]]:
    contexts: list[tuple[int, str]] = []
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    for paragraph in paragraphs:
        nums = extract_cited_numbers(paragraph, max_ref=max_ref)
        for num in nums:
            contexts.append((num, paragraph))
    return contexts


def extract_research_questions(body: str) -> list[str]:
    intro_match = re.search(
        r"1\.4[^\n]*Pregunta de investigación(.+?)(?:1\.5|CAPÍTULO II)",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    block_match = re.search(
        r"Pregunta de investigación(.+?)(?:Objetivo general|Objetivos específicos|Hipótesis|METODOLOG|Capítulo|\n3\.\s)",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    tema_match = re.search(
        r"(?is)Tema\s+de\s+(?:la\s+)?[Tt]esis\s*:?\s*(.+?)(?:\n\n|\n\d+\.)",
        body,
    )
    scope = intro_match.group(1) if intro_match else body
    if block_match:
        scope = block_match.group(1)
    questions = [_normalize(q) for q in RESEARCH_QUESTION.findall(scope)]
    if not questions:
        questions = [_normalize(q) for q in RESEARCH_QUESTION.findall(body)]
    if not questions and tema_match:
        tema = _normalize(tema_match.group(1))
        if len(tema) > 25:
            questions = [tema if tema.endswith("?") else f"¿{tema}?"]
    return questions


def _objectives_from_block(block: str) -> list[str]:
    chunks = re.split(r"(?m)^\d+\.\s+", block.strip())
    objectives: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 20 or re.search(r"\.{4,}", chunk):
            continue
        objectives.append(_normalize(chunk))
    if objectives:
        return objectives[:8]

    objectives = []
    for line in block.splitlines():
        line = line.strip()
        line = re.sub(r"^\d+[\).\s]+", "", line)
        if len(line) > 20 and not re.search(r"\.{4,}", line):
            objectives.append(_normalize(line))
    return objectives[:8]


def extract_objectives(body: str) -> list[str]:
    patterns = [
        r"(?is)(?:\d+(?:\.\d+)*\.?\s*)?Objetivos\s+espec[ií]ficos\s*(.+?)"
        r"(?=\n\s*(?:Supuestos|Hipótesis|CAPÍTULO|CAPITULO|SEGUNDA|TERCERA|CUARTA|QUINTA|"
        r"METODOLOG|MATERIALES|PARTE\s+[-–]|\Z))",
        r"1\.5\.2 Objetivos específicos(.+?)(?:CAPÍTULO II|CAPITULO II)",
        r"Objetivos específicos\s*\n(.+?)(?:\n5\.\s+Hipótesis|\nHipótesis de investigación|\nHipótesis|\n\d+\.\s+Metodolog|\nCapítulo|\nMETODOLOG)",
    ]
    for pattern in patterns:
        block_match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if not block_match:
            continue
        objectives = _objectives_from_block(block_match.group(1))
        if objectives:
            return objectives

    from savt.section_resolver import get_canonical_section

    obj_section = get_canonical_section(body, "objetivos")
    if obj_section:
        objectives = _objectives_from_block(obj_section)
        if objectives:
            return objectives
    return []


def extract_conclusions(body: str) -> str:
    bib = re.search(r"(?im)\nBIBLIOGRAF[IÍ]A\b", body)
    scope = body[: bib.start()] if bib else body

    inline_matches = list(
        re.finditer(
            r"(?im)(?:^|\n)\s*CONCLUSIONES(?:\s+GENERALES|\s+FINALES)?\b\s*",
            scope,
        )
    )
    for match in reversed(inline_matches):
        text = scope[match.end() :].strip()
        if count_words(text) > 150:
            return text

    headings = list(
        re.finditer(
            r"CAPÍTULO VI\.?\s*CONCLUSIONES(?:\d+)?\s*",
            scope,
            re.IGNORECASE,
        )
    )
    for heading in reversed(headings):
        start = heading.end()
        tail = scope[start:]
        end = re.search(r"BIBLIOGRAFÍA", tail, re.IGNORECASE)
        text = tail[: end.start()] if end else tail
        text = text.strip()
        if len(text) > 400:
            return text

    for pattern in [
        r"(?is)(?:CUARTA\s+PARTE[^\n]*\n)?\s*CONCLUSIONES(?:\s+GENERALES)?\s*\n(.+?)(?:\nBIBLIOGRAFÍA|\nREFERENCIAS|\Z)",
        r"(?m)^CONCLUSIONES(?:\s+GENERALES)?\s*\n(.+?)(?:\nBIBLIOGRAFÍA|\Z)",
        r"Conclusiones generales\s*\n(.+?)(?:\nBIBLIOGRAFÍA|\Z)",
    ]:
        match = re.search(pattern, scope, re.IGNORECASE | re.DOTALL)
        if match and len(match.group(1).strip()) > 400:
            return match.group(1).strip()

    from savt.section_resolver import get_canonical_section

    canonical = get_canonical_section(scope, "conclusiones")
    if len(canonical) > 400:
        return canonical

    return ""


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, re.UNICODE))


def estimate_pages(word_count: int, words_per_page: int = 300) -> float:
    return round(word_count / words_per_page, 1)


def _citations_from_bibliography(
    bibliography: dict[int, ReferenceEntry],
    style: str,
) -> tuple[set[int], set[str]]:
    """Las referencias se toman solo del apartado bibliográfico, no del cuerpo."""
    if style == "apa":
        keys = {ref.key for ref in bibliography.values() if ref.key}
        return set(), keys
    return set(bibliography.keys()), set()


def parse_thesis_file(source: BinaryIO | str, filename: str = "tesis.docx") -> dict:
    from savt.bibliography_styles import infer_topic_keywords_from_document
    from savt.document_pipeline import run_document_pipeline
    from savt.document_sections import extract_title
    from savt.pdf_parser import prepare_pdf_text
    from savt.text_normalize import normalize_full_document_text

    pdf_page_count = None
    norm_pages: list[str] | None = None
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        from savt.pdf_extraction_normalizer import normalize_pdf_extraction

        _full_raw, pdf_page_count, page_texts = prepare_pdf_text(source)
        pdf_extraction = normalize_pdf_extraction(page_texts)
        norm_pages = [
            normalize_full_document_text(page) for page in pdf_extraction["normalized_pages"]
        ]
        full_text = "\n".join(norm_pages)
    else:
        pdf_extraction = None
        full_text = normalize_full_document_text(extract_text_from_docx(source))

    pipeline = run_document_pipeline(
        full_text,
        page_texts=norm_pages,
        page_count=pdf_page_count,
    )

    body = pipeline["body"]
    bib_text = pipeline["bibliography_text"]
    section_map = pipeline["section_map"]
    section_meta = pipeline["section_meta"]
    bibliography = pipeline["bibliography"]
    citation_style = pipeline["citation_style"]
    cited_numbers = pipeline["cited_numbers"]
    cited_keys = pipeline["cited_keys"]

    sections = split_sections(body)
    conclusions = extract_conclusions(body)
    topic_keywords = infer_topic_keywords_from_document(full_text, body, filename)
    document_title = extract_title(full_text, filename)

    bib_words = count_words(bib_text)
    body_words = count_words(body)
    if pdf_page_count:
        page_estimate = float(pdf_page_count)
        page_estimate_body_only = float(pdf_page_count)
    else:
        page_estimate = estimate_pages(body_words + bib_words)
        page_estimate_body_only = estimate_pages(body_words)

    return {
        "filename": filename,
        "file_type": "pdf" if lower_name.endswith(".pdf") else "docx",
        "citation_style": citation_style,
        "full_text": full_text,
        "body": body,
        "bibliography_text": bib_text,
        "bibliography": bibliography,
        "sections": sections,
        "section_map": section_map,
        "section_meta": section_meta,
        "index_sections": pipeline["index_sections"],
        "structure_source": pipeline["structure_source"],
        "pipeline": pipeline["steps"],
        "cited_numbers": cited_numbers,
        "cited_keys": cited_keys,
        "citation_contexts": [],
        "citation_contexts_apa": [],
        "topic_keywords": topic_keywords,
        "document_title": document_title,
        "research_questions": extract_research_questions(body),
        "objectives": extract_objectives(body),
        "conclusions": conclusions,
        "word_count": body_words,
        "bibliography_word_count": bib_words,
        "page_estimate": page_estimate,
        "page_estimate_body_only": page_estimate_body_only,
        "pdf_page_count": pdf_page_count,
        "pdf_extraction": (
            {
                "original_text": pdf_extraction["original_text"],
                "normalized_text": pdf_extraction["normalized_text"],
            }
            if pdf_extraction
            else None
        ),
    }
