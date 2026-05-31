from __future__ import annotations

import re
import unicodedata

from savt.models import ReferenceEntry
from savt.parser import BIB_HEADING, _normalize, parse_bibliography

APA_CITATION_PATTERN = re.compile(
    r"\(([^()]*?\d{4}[a-z]?[^()]*?)\)",
    re.IGNORECASE,
)
APA_ENTRY_START = re.compile(
    r"(?ms)^([A-ZÁÉÍÓÚÑ][^\n]{3,180}?\(\d{4}[a-z]?\))",
)


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_author(value: str) -> str:
    value = strip_accents(value.lower()).strip()
    value = re.sub(r"[^a-z0-9\-]+", "-", value)
    return value.strip("-")


NAME_PARTICLES = {
    "van",
    "von",
    "de",
    "del",
    "la",
    "le",
    "da",
    "di",
    "du",
    "der",
    "den",
}

ORG_SYNONYMS = {
    "cepal": {"cepal", "eclac"},
    "eclac": {"cepal", "eclac"},
}


def extract_surname(author_text: str) -> str:
    author_text = author_text.strip().rstrip(".")
    if not author_text:
        return ""
    if "," in author_text:
        author_text = author_text.split(",")[0].strip()
    tokens = author_text.split()
    if not tokens:
        return ""
    if len(tokens) >= 2 and tokens[0].lower() in NAME_PARTICLES:
        return tokens[-1]
    if len(tokens) >= 2 and tokens[-1].lower() in NAME_PARTICLES:
        return tokens[-2]
    return tokens[-1]


def expand_apa_key(key: str) -> set[str]:
    if not key or "|" not in key:
        return set()
    author, year = key.split("|", 1)
    variants = {key}
    for alias in ORG_SYNONYMS.get(author, set()):
        variants.add(f"{alias}|{year}")
    return variants


def apa_keys_match(cited_key: str, bibliography_keys: set[str]) -> bool:
    return bool(expand_apa_key(cited_key) & bibliography_keys)


def apa_citation_key(citation: str) -> str:
    year_match = re.search(r"(\d{4})", citation)
    if not year_match:
        return ""
    year = year_match.group(1)
    author_part = citation[: year_match.start()].strip(" ,;")
    if " et al" in author_part.lower():
        first_author = author_part.split(" et al")[0].strip()
    elif "&" in author_part:
        first_author = author_part.split("&")[0].strip()
    elif ";" in author_part:
        first_author = author_part.split(";")[0].strip()
    elif "," in author_part:
        first_author = author_part.split(",")[0].strip()
    else:
        first_author = author_part.strip()
    surname = extract_surname(first_author)
    if not surname:
        return ""
    return f"{normalize_author(surname)}|{year}"


def apa_entry_key(entry: str) -> str:
    year_match = re.search(r"\((\d{4}[a-z]?)\)", entry)
    if not year_match:
        return ""
    year = year_match.group(1)[:4]
    head = entry.strip()[: year_match.start()].strip().rstrip(".")
    if "," in head:
        author_part = head.split(",")[0].strip()
    else:
        author_part = head.strip()
    surname = extract_surname(author_part)
    if not surname:
        return ""
    return f"{normalize_author(surname)}|{year}"


def detect_citation_style(body: str, bib_text: str) -> str:
    numbered_entries = len(re.findall(r"(?m)^\d+\.\s*\S", bib_text))
    apa_entries = len(APA_ENTRY_START.findall(bib_text))
    apa_citations = sum(
        1
        for match in APA_CITATION_PATTERN.finditer(body)
        if re.search(r"[A-Za-zÁÉÍÓÚáéíóúñ]{3}.*,\s*\d{4}", match.group(1))
    )
    numbered_citations = len(re.findall(r"\(\d+\)", body))

    if apa_entries >= 5 and apa_citations >= numbered_citations:
        return "apa"
    if numbered_entries >= 5:
        return "numbered"
    if apa_citations > numbered_citations:
        return "apa"
    return "numbered"


def parse_apa_bibliography(bib_text: str) -> dict[int, ReferenceEntry]:
    entries: dict[int, ReferenceEntry] = {}
    if not bib_text:
        return entries

    starts = [match.start() for match in APA_ENTRY_START.finditer(bib_text)]
    if not starts:
        return entries

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(bib_text)
        index = i + 1
        raw = _normalize(bib_text[start:end])
        doi_match = re.search(r"https?://doi\.org/([^\s]+)", raw, re.IGNORECASE)
        if not doi_match:
            doi_match = re.search(r"doi[:.]?\s*(10\.\S+)", raw, re.IGNORECASE)
        year_match = re.search(r"\((\d{4}[a-z]?)\)", raw)
        key = apa_entry_key(raw)
        entries[index] = ReferenceEntry(
            number=index,
            key=key,
            raw=raw,
            title=raw[:180],
            doi=doi_match.group(1).rstrip(".,;") if doi_match else "",
            year=year_match.group(1)[:4] if year_match else "",
        )
    return entries


def extract_apa_citations(body: str) -> tuple[set[str], list[tuple[str, str]]]:
    cited_keys: set[str] = set()
    contexts: list[tuple[str, str]] = []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if len(p.split()) > 8]
    for paragraph in paragraphs:
        keys_in_paragraph: set[str] = set()
        for match in APA_CITATION_PATTERN.finditer(paragraph):
            inner = match.group(1)
            if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúñ]{3}.*,\s*\d{4}", inner):
                continue
            key = apa_citation_key(inner)
            if key:
                keys_in_paragraph.add(key)
        for key in keys_in_paragraph:
            cited_keys.add(key)
            contexts.append((key, paragraph))
    return cited_keys, contexts


def parse_bibliography_by_style(bib_text: str, style: str) -> dict[int, ReferenceEntry]:
    if style == "apa":
        return parse_apa_bibliography(bib_text)
    return parse_bibliography(bib_text)


def infer_topic_keywords(body: str, filename: str) -> list[str]:
    title_match = re.search(
        r"(?ms)(TRABAJO FINAL|TÍTULO:|TESIS)\s*(.+?)\n\n",
        body[:5000],
        re.IGNORECASE,
    )
    title = title_match.group(2) if title_match else filename
    words = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñ]{5,}", strip_accents(title.lower()))
    stop = {
        "trabajo",
        "final",
        "tesis",
        "maestria",
        "universidad",
        "presentacion",
        "analisis",
        "estudio",
        "investigacion",
    }
    return [word for word in words if word not in stop][:12]
