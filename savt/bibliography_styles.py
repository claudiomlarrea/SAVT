from __future__ import annotations

import re
import unicodedata

from savt.models import ReferenceEntry
from savt.parser import BIB_HEADING, _normalize, parse_bibliography
from savt.text_normalize import normalize_bibliography_text

APA_CITATION_PATTERN = re.compile(
    r"\(([^()]*?\d{4}[a-z]?[^()]*?)\)",
    re.IGNORECASE,
)
# Bloque autor(es) hasta (AAAA) — tolera PDFs con entradas pegadas y apellidos compuestos.
_NAME_PARTICLE = r"(?:van|von|de|del|da|di|du|der|den|la|le|y|e)"
_APA_SURNAME = (
    rf"(?:(?:{_NAME_PARTICLE}\s+)?[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñüöäÜÖÄ\-]+"
    rf"(?:\s+(?:{_NAME_PARTICLE}\s+)?[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñüöäÜÖÄ\-]+)*)"
)
_APA_YEAR = r"\(\d{4}[a-z]?(?:,\s*[A-Za-z]+)?\)"
_APA_AUTHOR_BLOCK = re.compile(
    rf"{_APA_SURNAME},\s+[A-ZÁÉÍÓÚÑ]\.(?:\s*\n\s*)?"
    rf"(?:(?!(?:https?://|doi\.org/))[\s\S]){{0,400}}?{_APA_YEAR}",
)
_APA_ORG_BLOCK = re.compile(
    rf"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñ\s&\-]{{2,80}}\.\s+{_APA_YEAR}",
)
_APA_URL_BEFORE_ENTRY = re.compile(r"(?:doi\.org/\S+|https?://\S+)\s*$")

# Compatibilidad con detectores que usan inicio de línea.
APA_ENTRY_START = re.compile(
    r"(?ms)^([A-ZÁÉÍÓÚÑ0-9][^\n]{2,220}?\(\d{4}[a-z]?\))",
)
APA_ENTRY_FALLBACK = re.compile(
    r"(?ms)(?:^|\n)([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñ0-9.,\-\s&]{2,120}?\(\d{4}[a-z]?\))",
)

INSTITUTIONAL_CITATIONS = {
    "argentina",
    "chile",
    "brasil",
    "mexico",
    "uruguay",
    "colombia",
    "espana",
    "spain",
    "oecd",
    "unesco",
    "cepal",
    "eclac",
    "onu",
    "naciones unidas",
    "world bank",
    "bm",
    "fmi",
    "imf",
}


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
    "oecd": {"oecd"},
    "unesco": {"unesco"},
    "onu": {"onu", "naciones-unidas", "united-nations"},
    "naciones-unidas": {"onu", "naciones-unidas", "united-nations"},
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
    if len(tokens) == 1:
        return tokens[0].rstrip(".")
    if len(tokens) >= 3 and tokens[-2].lower() in NAME_PARTICLES:
        return tokens[-1]
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
    if expand_apa_key(cited_key) & bibliography_keys:
        return True
    if "|" not in cited_key:
        return False
    author, year = cited_key.split("|", 1)
    for key in bibliography_keys:
        if not key or "|" not in key:
            continue
        bib_author, bib_year = key.split("|", 1)
        if bib_year != year:
            continue
        if author == bib_author:
            return True
        if author in bib_author or bib_author in author:
            return True
    return False


def citation_present_in_bibliography_text(cited_key: str, bib_text: str) -> bool:
    """Respaldo cuando el PDF corrompe apellidos (p. ej. «Plaza de la Hoz»)."""
    if "|" not in cited_key or not bib_text:
        return False
    author, year = cited_key.split("|", 1)
    author = re.escape(author)
    patterns = [
        rf"(?i)\b{author}\b.{{0,220}}\({year}",
        rf"(?i){author}.{{0,220}}\({year}",
    ]
    return any(re.search(p, bib_text) for p in patterns)


def _citation_year(citation: str) -> str:
    year_match = re.search(r"(\d{4})", citation)
    return year_match.group(1) if year_match else ""


def apa_citation_key(citation: str) -> str:
    year = _citation_year(citation)
    if not year:
        return ""
    year_match = re.search(r"(\d{4})", citation)
    author_part = citation[: year_match.start()].strip(" ,;–-")
    author_part = re.sub(r"\s*[–-]\s*\d{4}\s*$", "", author_part).strip()

    if " et al" in author_part.lower():
        first_author = author_part.split(" et al")[0].strip()
    elif "&" in author_part:
        first_author = author_part.split("&")[0].strip()
    elif ";" in author_part:
        first_author = author_part.split(";")[0].strip()
    elif "," in author_part and not re.match(r"^[A-Z]{2,}$", author_part.strip()):
        first_author = author_part.split(",")[0].strip()
    else:
        first_author = author_part.strip()

    surname = extract_surname(first_author)
    if not surname:
        return ""
    return f"{normalize_author(surname)}|{year}"


def apa_entry_key(entry: str) -> str:
    year_match = re.search(r"\((\d{4}[a-z]?)(?:,\s*[A-Za-z]+)?\)", entry)
    if not year_match:
        return ""
    year = year_match.group(1)[:4]
    head = entry.strip()[: year_match.start()].strip().rstrip(".")
    if "," in head:
        author_part = head.split(",")[0].strip()
    else:
        author_part = head.strip().rstrip(".")
    surname = extract_surname(author_part)
    if not surname:
        return ""
    return f"{normalize_author(surname)}|{year}"


def detect_citation_style(body: str, bib_text: str) -> str:
    numbered_entries = len(re.findall(r"(?m)^\d+\.\s*\S", bib_text))
    apa_entries = len(_collect_apa_starts(bib_text)) if bib_text else 0
    if apa_entries < 5:
        apa_entries = len(APA_ENTRY_START.findall(bib_text)) + len(APA_ENTRY_FALLBACK.findall(bib_text))
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


def _strip_bibliography_heading(bib_text: str) -> str:
    return re.sub(r"^(?:\s*BIBLIOGRAF[IÍ]A\s*)", "", bib_text, flags=re.I)


def _is_apa_entry_start(bib_text: str, pos: int) -> bool:
    if pos == 0:
        return True
    prefix = bib_text[max(0, pos - 280):pos]
    if prefix.endswith("\n"):
        return True
    if _APA_URL_BEFORE_ENTRY.search(prefix.rstrip()):
        return True
    tail = prefix.rstrip()[-120:]
    if re.search(rf"{_APA_YEAR}\.\s*$", tail):
        return True
    return False


def _collect_apa_starts(bib_text: str) -> list[int]:
    bib_text = normalize_bibliography_text(bib_text)
    body = _strip_bibliography_heading(bib_text)
    offset = len(bib_text) - len(body)

    starts: set[int] = set()
    for pattern in (_APA_AUTHOR_BLOCK, _APA_ORG_BLOCK):
        for match in pattern.finditer(body):
            if _is_apa_entry_start(body, match.start()):
                starts.add(match.start() + offset)

    if len(starts) < 5:
        for match in APA_ENTRY_START.finditer(bib_text):
            starts.add(match.start())
        for match in APA_ENTRY_FALLBACK.finditer(bib_text):
            starts.add(match.start(1))

    return sorted(starts)


def parse_apa_bibliography(bib_text: str) -> dict[int, ReferenceEntry]:
    entries: dict[int, ReferenceEntry] = {}
    if not bib_text:
        return entries

    bib_text = normalize_bibliography_text(bib_text)
    starts = _collect_apa_starts(bib_text)
    if not starts:
        return entries

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(bib_text)
        index = i + 1
        raw = _normalize(bib_text[start:end])
        doi_match = re.search(r"https?://doi\.org/([^\s]+)", raw, re.IGNORECASE)
        if not doi_match:
            doi_match = re.search(r"doi[:.]?\s*(10\.\S+)", raw, re.IGNORECASE)
        year_match = re.search(r"\((\d{4}[a-z]?)(?:,\s*[A-Za-z]+)?\)", raw)
        doi_value = doi_match.group(1).rstrip(".,;") if doi_match else ""
        doi_value = re.sub(r"^https?://doi\.org/", "", doi_value, flags=re.I)
        key = apa_entry_key(raw)
        entries[index] = ReferenceEntry(
            number=index,
            key=key,
            raw=raw,
            title=raw[:180],
            doi=doi_value,
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
            inner = re.sub(r"\s+", " ", match.group(1)).strip()
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
    return parse_bibliography(normalize_bibliography_text(bib_text))


def infer_topic_keywords_from_document(full_text: str, body: str, filename: str) -> list[str]:
    from savt.document_sections import infer_topic_keywords

    return infer_topic_keywords(full_text, body, filename)


def is_institutional_citation_key(key: str) -> bool:
    if "|" not in key:
        return False
    author = key.split("|", 1)[0]
    return author in INSTITUTIONAL_CITATIONS or author in {"argentina", "oecd", "unesco"}


def topical_match(reference: ReferenceEntry, keywords: list[str]) -> bool:
    if not keywords:
        return True
    ref_norm = strip_accents((reference.raw + " " + (reference.title or "")).lower())
    hits = 0
    for keyword in keywords:
        kw = strip_accents(keyword.lower())
        if len(kw) < 4:
            continue
        if kw in ref_norm:
            hits += 1
            continue
        if len(kw) >= 5 and any(kw[:4] in token for token in re.findall(r"[a-z]{4,}", ref_norm)):
            hits += 1
    # Referencias interdisciplinarias: basta con coincidir un término clave.
    return hits >= 1


def infer_topic_keywords(body: str, filename: str) -> list[str]:
    """Compatibilidad retroactiva: usa solo cuerpo si no hay full_text."""
    return infer_topic_keywords_from_document(body, body, filename)
