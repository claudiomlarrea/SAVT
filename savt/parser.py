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
BIB_HEADING = re.compile(r"^BIBLIOGRAFÍA\s*$", re.IGNORECASE | re.MULTILINE)
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
        return full_text, ""
    idx = match[-1].start()
    return full_text[:idx].strip(), full_text[idx:].strip()


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


def parse_bibliography(bib_text: str) -> dict[int, ReferenceEntry]:
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
            flush()
            current_num = int(m.group(1))
            buffer = [m.group(2)]
        elif current_num is not None:
            buffer.append(line)
    flush()
    return entries


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


def extract_cited_numbers(body: str, max_ref: int = 500) -> set[int]:
    cited: set[int] = set()
    for match in re.finditer(r"\((\d+(?:[,\s\-–]\d+)*)\)", body):
        chunk = match.group(1)
        for part in re.split(r"[,\s\-–]+", chunk):
            if part.isdigit():
                num = int(part)
                if 1 <= num <= max_ref:
                    cited.add(num)
    return cited


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
    scope = intro_match.group(1) if intro_match else body
    if block_match:
        scope = block_match.group(1)
    questions = [_normalize(q) for q in RESEARCH_QUESTION.findall(scope)]
    if not questions:
        questions = [_normalize(q) for q in RESEARCH_QUESTION.findall(body)]
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
    return []


def extract_conclusions(body: str) -> str:
    headings = list(
        re.finditer(
            r"CAPÍTULO VI\.?\s*CONCLUSIONES(?:\d+)?\s*",
            body,
            re.IGNORECASE,
        )
    )
    for heading in reversed(headings):
        start = heading.end()
        tail = body[start:]
        end = re.search(r"BIBLIOGRAFÍA", tail, re.IGNORECASE)
        text = tail[: end.start()] if end else tail
        text = text.strip()
        if len(text) > 400:
            return text

    for pattern in [
        r"(?m)^CONCLUSIONES(?:\s+GENERALES)?\s*\n(.+?)(?:\nBIBLIOGRAFÍA|\Z)",
        r"Conclusiones generales\s*\n(.+?)(?:\nBIBLIOGRAFÍA|\Z)",
    ]:
        match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if match and len(match.group(1).strip()) > 400:
            return match.group(1).strip()

    match = re.search(
        r"CONCLUSIONES(.+?)(?:BIBLIOGRAFÍA|$)",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, re.UNICODE))


def estimate_pages(word_count: int, words_per_page: int = 300) -> float:
    return round(word_count / words_per_page, 1)


def parse_thesis_file(source: BinaryIO | str, filename: str = "tesis.docx") -> dict:
    from savt.bibliography_styles import (
        detect_citation_style,
        extract_apa_citations,
        infer_topic_keywords,
        parse_bibliography_by_style,
    )
    from savt.pdf_parser import prepare_pdf_text, remove_pdf_front_matter

    pdf_page_count = None
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        full_text, pdf_page_count = prepare_pdf_text(source)
        body_raw, bib_text = split_body_and_bibliography(full_text)
        body = remove_pdf_front_matter(body_raw)
    else:
        full_text = extract_text_from_docx(source)
        body_raw, bib_text = split_body_and_bibliography(full_text)
        body = remove_index_duplicate(body_raw)

    citation_style = detect_citation_style(body, bib_text)
    bibliography = parse_bibliography_by_style(bib_text, citation_style)
    sections = split_sections(body)
    topic_keywords = infer_topic_keywords(body, filename)

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
        "cited_numbers": cited_numbers,
        "cited_keys": cited_keys,
        "citation_contexts": citation_contexts_numbered,
        "citation_contexts_apa": citation_contexts_keys,
        "topic_keywords": topic_keywords,
        "research_questions": extract_research_questions(body),
        "objectives": extract_objectives(body),
        "conclusions": extract_conclusions(body),
        "word_count": body_words,
        "bibliography_word_count": bib_words,
        "page_estimate": page_estimate,
        "page_estimate_body_only": page_estimate_body_only,
        "pdf_page_count": pdf_page_count,
    }
