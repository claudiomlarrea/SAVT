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
NUMERIC_CITATION_PATTERN = re.compile(r"\((\d+(?:[,\s\-–]\d+)*)\)")
NUMBERED_BIB_ENTRY_START = re.compile(
    r"(?m)^(\d+)\.\s+([A-Za-zÁÉÍÓÚáéíóúñ\"(].*)"
)
STATISTICAL_CONTEXT = re.compile(
    r"(?i)(?:\bp\s*[<>=]|significativ|intervalo\s+de\s+confianza|"
    r"nivel\s+de\s+significancia|\bic\s*\(|\bvalor\s+p\b|\balpha\b|\bα\b)"
)
BIB_HEADING = re.compile(
    r"(?m)(?:^|\n)\s*BIBLIOGRAF[IÍ]A(?:\s*$|\s+(?=[A-ZÁÉÍÓÚÑ]))",
    re.IGNORECASE | re.MULTILINE,
)
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
    match = list(BIB_HEADING.finditer(full_text))
    if not match:
        alt = re.search(r"(?m)(?:^|\n)\s*REFERENCIAS(?:\s*$|\s+(?=[A-ZÁÉÍÓÚÑ]))", full_text, re.I)
        if alt:
            idx = alt.start()
            return full_text[:idx].strip(), full_text[idx:].strip()
        return full_text, ""
    idx = match[-1].start()
    body = full_text[:idx].strip()
    bib = full_text[idx:].strip()
    bib = re.sub(r"^BIBLIOGRAF[IÍ]A\s*", "BIBLIOGRAFÍA\n", bib, flags=re.IGNORECASE)
    bib = re.sub(r"^REFERENCIAS\s*", "REFERENCIAS\n", bib, flags=re.IGNORECASE)
    return body, bib


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
    body = re.sub(r"^\d+\.\s*", "", raw)
    if re.match(r"(?i)(?:disponible|available)\b", body):
        return False
    if not re.match(r'[A-ZÁÉÍÓÚa-z"(]', body):
        return False
    if sum(char.isdigit() for char in body) / max(len(body), 1) > 0.35:
        return False
    if re.search(r"\b(19|20)\d{2}\b", raw):
        return True
    if re.search(r"doi|PMID|https?://|Journal|Rev\.|vol\.", raw, re.I):
        return True
    if re.search(r"[A-ZÁÉÍÓÚa-z][A-Za-zÁÉÍÓÚáéíóúñ'\-]+,\s+[A-Z]", raw):
        return True
    return len(body) > 80


def _build_reference_entry(number: int, raw: str) -> ReferenceEntry:
    doi_match = re.search(r"doi[:.]?\s*(10\.\S+)", raw, re.IGNORECASE)
    pmid_match = re.search(r"PMID:\s*(\d+)", raw, re.IGNORECASE)
    year_match = re.search(r"\b(19|20)\d{2}\b", raw)
    year = year_match.group(0) if year_match else ""
    if year and not (1900 <= int(year) <= 2030):
        paren_year = re.search(r"\((\d{4}[a-z]?)\)", raw)
        year = paren_year.group(1)[:4] if paren_year else ""
    title = raw.split(". ", 1)[1][:180] if ". " in raw else raw[:180]
    return ReferenceEntry(
        number=number,
        raw=raw,
        title=title,
        doi=doi_match.group(1).rstrip(".,;") if doi_match else "",
        pmid=pmid_match.group(1) if pmid_match else "",
        year=year,
    )


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


def parse_numbered_bibliography(bib_text: str) -> dict[int, ReferenceEntry]:
    if not bib_text:
        return {}

    cleaned = re.sub(
        r"^(?:\s*BIBLIOGRAF[IÍ]A|REFERENCIAS)\s*\n?",
        "",
        bib_text,
        flags=re.IGNORECASE,
    )
    matches = list(NUMBERED_BIB_ENTRY_START.finditer(cleaned))
    entries: dict[int, ReferenceEntry] = {}

    for index, match in enumerate(matches):
        number = int(match.group(1))
        if number < 1 or number > 999:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        raw = _normalize(cleaned[match.start() : end])
        if not _looks_like_bibliography_entry(raw):
            continue
        if number not in entries or len(raw) > len(entries[number].raw):
            entries[number] = _build_reference_entry(number, raw)

    if entries:
        return trim_numbered_bibliography_range(entries)
    return parse_bibliography_line_by_line(bib_text)


def parse_bibliography_line_by_line(bib_text: str) -> dict[int, ReferenceEntry]:
    entries: dict[int, ReferenceEntry] = {}
    if not bib_text:
        return entries

    current_num: int | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_num, buffer
        if current_num is None:
            return
        raw = _normalize(" ".join(buffer))
        doi_match = re.search(r"doi[:.]?\s*(10\.\S+)", raw, re.IGNORECASE)
        pmid_match = re.search(r"PMID:\s*(\d+)", raw, re.IGNORECASE)
        year_match = re.search(r"\b(19|20)\d{2}\b", raw)
        year = year_match.group(0) if year_match else ""
        if year and not (1900 <= int(year) <= 2030):
            paren_year = re.search(r"\((\d{4}[a-z]?)\)", raw)
            year = paren_year.group(1)[:4] if paren_year else ""
        if not _looks_like_bibliography_entry(raw):
            current_num = None
            buffer = []
            return
        title = raw
        if ". " in raw:
            title = raw.split(". ", 1)[1][:180]
        entries[current_num] = ReferenceEntry(
            number=current_num,
            raw=raw,
            title=title,
            doi=doi_match.group(1).rstrip(".,;") if doi_match else "",
            pmid=pmid_match.group(1) if pmid_match else "",
            year=year,
        )
        current_num = None
        buffer = []

    for line in bib_text.splitlines():
        line = line.strip()
        if not line or BIB_HEADING.match(line):
            continue
        m = re.match(r"^(\d+)\.\s*(.*)", line)
        if m:
            number = int(m.group(1))
            if number < 1 or number > 999:
                continue
            rest = m.group(2).strip()
            if not rest and not re.match(r"^\d+\.\s*$", line):
                continue
            flush()
            current_num = number
            buffer = [rest] if rest else []
        elif current_num is not None:
            buffer.append(line)
    flush()
    return trim_numbered_bibliography_range(entries)


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
    before = body[max(0, start - 120) : start]
    if STATISTICAL_CONTEXT.search(before):
        if len(numbers) == 1 and numbers[0] > 100:
            return True
    return False


def count_numeric_citation_appearances(body: str, max_ref: int = 500) -> int:
    appearances = 0
    for match in NUMERIC_CITATION_PATTERN.finditer(body):
        chunk = match.group(1)
        if _is_false_positive_numeric_citation(chunk, body, match.start()):
            continue
        appearances += 1
    return appearances


def extract_cited_numbers(body: str, max_ref: int = 500) -> set[int]:
    cited: set[int] = set()
    for match in NUMERIC_CITATION_PATTERN.finditer(body):
        chunk = match.group(1)
        if _is_false_positive_numeric_citation(chunk, body, match.start()):
            continue
        for part in re.split(r"[,\s\-–]+", chunk):
            if part.isdigit():
                num = int(part)
                if 1 <= num <= max_ref:
                    cited.add(num)
    return cited


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


def parse_thesis_file(source: BinaryIO | str, filename: str = "tesis.docx") -> dict:
    from savt.bibliography_styles import (
        detect_citation_style,
        extract_apa_citations,
        infer_topic_keywords_from_document,
        parse_bibliography_by_style,
    )
    from savt.document_sections import extract_title
    from savt.pdf_parser import prepare_pdf_text, remove_pdf_front_matter
    from savt.text_normalize import normalize_full_document_text

    pdf_page_count = None
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        full_text, pdf_page_count = prepare_pdf_text(source)
        full_text = normalize_full_document_text(full_text)
        body_raw, bib_text = split_body_and_bibliography(full_text)
        body = remove_pdf_front_matter(body_raw)
    else:
        full_text = extract_text_from_docx(source)
        body_raw, bib_text = split_body_and_bibliography(full_text)
        body = remove_index_duplicate(body_raw)

    citation_style = detect_citation_style(body, bib_text)
    bibliography = parse_bibliography_by_style(bib_text, citation_style)
    sections = split_sections(body)
    conclusions = extract_conclusions(body)
    from savt.section_resolver import build_enriched_section_map

    section_map, section_meta = build_enriched_section_map(
        body,
        conclusions_text=conclusions,
    )
    topic_keywords = infer_topic_keywords_from_document(full_text, body, filename)
    document_title = extract_title(full_text, filename)

    if citation_style == "apa":
        cited_keys, citation_contexts = extract_apa_citations(body)
        cited_numbers: set[int] = set()
        citation_contexts_numbered: list[tuple[int, str]] = []
        citation_contexts_keys: list[tuple[str, str]] = citation_contexts
    else:
        cited_keys = set()
        cited_numbers = extract_cited_numbers(body, max_ref=max(bibliography.keys(), default=500))
        citation_contexts_numbered = extract_citation_contexts(
            body, max_ref=max(bibliography.keys(), default=500)
        )
        citation_contexts_keys = []

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
        "cited_numbers": cited_numbers,
        "cited_keys": cited_keys,
        "citation_contexts": citation_contexts_numbered,
        "citation_contexts_apa": citation_contexts_keys,
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
    }
