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
BRACKET_APA_CITATION_PATTERN = re.compile(
    r"\[([^[\]]*?\d{4}[a-z]?[^[\]]*?)\]",
    re.IGNORECASE,
)
# Bloque autor(es) hasta (AAAA) — tolera PDFs con entradas pegadas y apellidos compuestos.
_NAME_PARTICLE = r"(?:van|von|de|del|da|di|du|der|den|la|le|y|e)"
_APA_SURNAME = (
    rf"(?:(?:{_NAME_PARTICLE}\s+)?[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñüöäÜÖÄ\-]+"
    rf"(?:\s+(?:{_NAME_PARTICLE}\s+)?[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñüöäÜÖÄ\-]+)*)"
)
_APA_YEAR = r"(?:\s|,)\s*\(\d{4}[a-z]?(?:,\s*[A-Za-z]+)?\)"
_APA_AUTHOR_BLOCK = re.compile(
    rf"{_APA_SURNAME},\s+[A-ZÁÉÍÓÚÑ]\.(?:\s*\n\s*)?"
    rf"(?:(?!(?:https?://|doi\.org/))[\s\S]){{0,400}}?{_APA_YEAR}",
)
_APA_ORG_BLOCK = re.compile(
    rf"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñ\s&\-]{{2,80}}\.\s+{_APA_YEAR}",
)
_APA_URL_BEFORE_ENTRY = re.compile(r"(?:doi\.org/\S+|https?://\S+)\s*$")

# Compatibilidad con detectores que usan inicio de línea.
_BIB_BULLET_PREFIX = r"(?:[\uf0a7\uf0b7\uf076\uf0d8\u25aa\u25cf\u25cb\u2022▪•➤►]\s*)?"
APA_ENTRY_START = re.compile(
    rf"(?ms)^(?:{_BIB_BULLET_PREFIX})([A-ZÁÉÍÓÚÑ0-9][^\n]{{2,240}}?(?:\s|,)\s*\(\d{{4}}[a-z]?\))",
)
APA_ENTRY_FALLBACK = re.compile(
    rf"(?ms)(?:^|\n)(?:{_BIB_BULLET_PREFIX})([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñ0-9.,\-\s&]{{2,160}}?(?:\s|,)\s*\(\d{{4}}[a-z]?\))",
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
    "dos",
    "das",
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
    if len(tokens) >= 2 and tokens[0].lower() in NAME_PARTICLES:
        if len(tokens) >= 3 and tokens[1].lower() in NAME_PARTICLES:
            return tokens[-1]
        return "-".join(tokens[1:]) if len(tokens) > 2 else tokens[-1]
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
    if "-" in author:
        tail = author.split("-")[-1]
        if len(tail) >= 3:
            variants.add(f"{tail}|{year}")
    for particle in ("dos", "de", "del", "van", "von"):
        prefix = f"{particle}-"
        if author.startswith(prefix):
            rest = author[len(prefix) :]
            if rest:
                variants.add(f"{rest}|{year}")
    if year[:4].isdigit():
        y = int(year[:4])
        for delta in (-1, 1):
            y2 = y + delta
            if 1900 <= y2 <= 2030:
                variants.add(f"{author}|{y2}")
    return variants


def _authors_compatible(cited_author: str, bib_author: str) -> bool:
    if not cited_author or not bib_author:
        return False
    if cited_author == bib_author:
        return True
    if cited_author in bib_author or bib_author in cited_author:
        return True
    if cited_author.split("-")[-1] == bib_author.split("-")[-1]:
        return True
    if len(cited_author) >= 5 and len(bib_author) >= 5 and cited_author[:5] == bib_author[:5]:
        return True
    return False


def apa_keys_match(cited_key: str, bibliography_keys: set[str]) -> bool:
    if expand_apa_key(cited_key) & bibliography_keys:
        return True
    if "|" not in cited_key:
        return False
    author, year = cited_key.split("|", 1)
    year = year[:4]
    for key in bibliography_keys:
        if not key or "|" not in key:
            continue
        bib_author, bib_year = key.split("|", 1)
        bib_year = bib_year[:4]
        if bib_year != year:
            if not (year.isdigit() and bib_year.isdigit() and abs(int(year) - int(bib_year)) == 1):
                continue
        if _authors_compatible(author, bib_author):
            return True
    return False


def _prepare_bibliography_search_text(bib_text: str) -> str:
    if not bib_text:
        return ""
    text = strip_accents(bib_text.lower())
    return re.sub(r"\s+", " ", text)


def _author_variants_for_search(author_norm: str) -> list[str]:
    """Variantes de apellido normalizado para buscar en bibliografía (partículas, compuestos)."""
    if not author_norm:
        return []
    seen: set[str] = set()
    ordered: list[str] = []

    def add(value: str) -> None:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)

    add(author_norm)
    if "-" in author_norm:
        add(author_norm.split("-")[-1])
        add(author_norm.replace("-", ""))
    for particle in ("dos", "de", "del", "van", "von", "da"):
        prefix = f"{particle}-"
        if author_norm.startswith(prefix):
            add(author_norm[len(prefix) :])
    # Citas «Dos Santos» → clave santos|año; en bibliografía suele figurar «dos santos».
    if "-" not in author_norm and len(author_norm) >= 3:
        add(f"dos-{author_norm}")
        add(f"de-{author_norm}")
    return ordered


def _author_variant_pattern(variant: str) -> str:
    parts = [p for p in variant.split("-") if p]
    if not parts:
        return re.escape(variant)
    if len(parts) == 1:
        return re.escape(parts[0])
    return r"[\-\s,]+".join(re.escape(p) for p in parts)


def citation_present_in_bibliography_text(
    cited_key: str,
    bib_text: str,
    *,
    max_gap: int = 450,
    year_slack: int = 1,
) -> bool:
    """Respaldo cuando el PDF corrompe apellidos o la clave autor|año no coincide exactamente."""
    if "|" not in cited_key or not bib_text:
        return False
    author, year = cited_key.split("|", 1)
    year = year[:4]
    if not year.isdigit():
        return False
    search_text = _prepare_bibliography_search_text(bib_text)
    years = {year}
    y = int(year)
    for delta in range(-year_slack, year_slack + 1):
        y2 = y + delta
        if 1900 <= y2 <= 2030:
            years.add(str(y2))

    for variant in _author_variants_for_search(author):
        author_pat = _author_variant_pattern(variant)
        for y in years:
            pattern = rf"(?<![a-z]){author_pat}(?:[^a-z]|[a-z](?!{re.escape(y)})){{0,{max_gap}}}\({y}"
            if re.search(pattern, search_text):
                return True
    return False


def supplemental_bibliography_keys(parsed: dict) -> set[str]:
    """Claves autor|año inferidas de todas las secciones REFERENCIAS del documento."""
    from savt.citations import merged_bibliography_search_text

    corpus = merged_bibliography_search_text(parsed)
    if not corpus.strip():
        return set()
    extra = parse_apa_bibliography(corpus)
    return {ref.key for ref in extra.values() if ref.key}


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
    year_match = re.search(r"(?:\s|,)\s*\((\d{4}[a-z]?)(?:,\s*[A-Za-z]+)?\)", entry)
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
    """Elige APA o Vancouver según qué parser recupere más referencias válidas."""
    if not bib_text or not bib_text.strip():
        return "apa"

    normalized = normalize_bibliography_text(bib_text)
    apa_parsed = len(parse_apa_bibliography(normalized))
    numbered_parsed = len(parse_bibliography(normalized))

    if apa_parsed >= 5 and apa_parsed >= numbered_parsed:
        return "apa"
    if numbered_parsed >= 5 and numbered_parsed > apa_parsed:
        return "numbered"

    apa_hints = len(_collect_apa_starts(normalized))
    if apa_hints < 5:
        apa_hints = len(APA_ENTRY_START.findall(normalized)) + len(APA_ENTRY_FALLBACK.findall(normalized))
    # Solo números bajos al inicio de línea (1.–200.); evita páginas/volúmenes en APA.
    numbered_hints = len(
        re.findall(r"(?m)^\s*(?:\[?[1-9]\d{0,2}\]?\.)\s+[A-Za-zÁÉÍÓÚ\"'(]", normalized)
    )
    vancouver_hints = len(
        re.findall(
            r"(?m)^\s*\d{1,3}\.\s+[A-ZÁÉÍÓÚÑ][^\n]{10,}(?:\[Internet\]|Available from:|\[Cited)",
            normalized,
        )
    )
    numbered_hints = max(numbered_hints, vancouver_hints)

    if apa_hints >= 10 and apa_hints >= numbered_hints:
        return "apa"
    if numbered_hints >= 5 and numbered_hints > apa_hints:
        return "numbered"
    if apa_hints >= 3:
        return "apa"
    if numbered_hints > 0:
        return "numbered"
    return "apa"


def _strip_bibliography_heading(bib_text: str) -> str:
    return re.sub(r"^(?:\s*BIBLIOGRAF[IÍ]A\s*)", "", bib_text, flags=re.I)


def _is_apa_entry_start(bib_text: str, pos: int) -> bool:
    if pos == 0:
        return True
    prefix = bib_text[max(0, pos - 280):pos]
    if prefix.endswith("\n"):
        return True
    if re.search(rf"(?:^|\n)\s*{_BIB_BULLET_PREFIX}$", prefix):
        return True
    if _APA_URL_BEFORE_ENTRY.search(prefix.rstrip()):
        return True
    tail = prefix.rstrip()[-120:]
    if re.search(rf"{_APA_YEAR}\.?\s*$", tail):
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
        year_match = re.search(r"(?:\s|,)\s*\((\d{4}[a-z]?)(?:,\s*[A-Za-z]+)?\)", raw)
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


NARRATIVE_APA_PATTERN = re.compile(
    r"([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚáéíóúñ''\-\.]+(?:\s+(?:y|&)\s+[\wÁÉÍÓÚáéíóúñ''\-\.]+)+)\s*\((\d{4}[a-z]?)\)",
)
NARRATIVE_APA_ET_AL_PATTERN = re.compile(
    r"([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚáéíóúñ''\-\.\s]{2,80}?\s+et al\.)\s*\((\d{4}[a-z]?)\)",
)


def _narrative_author_surnames(author_text: str) -> list[str]:
    author_text = author_text.strip()
    if not author_text:
        return []
    if re.search(r"\bet al\.\s*$", author_text, re.IGNORECASE):
        author_text = re.sub(r"\s+et al\.\s*$", "", author_text, flags=re.IGNORECASE).strip()
    parts = re.split(r"\s+(?:y|&)\s+", author_text, flags=re.IGNORECASE)
    return [normalize_author(extract_surname(part.strip())) for part in parts if part.strip()]


def extract_narrative_apa_keys(body: str, bibliography: dict[int, ReferenceEntry]) -> set[str]:
    """Citas narrativas APA del tipo «Autor (año)» o «Autor et al. (año)»."""
    keys: set[str] = set()
    if not body or not bibliography:
        return keys
    matches: list[tuple[str, str]] = []
    for pattern in (NARRATIVE_APA_PATTERN, NARRATIVE_APA_ET_AL_PATTERN):
        for match in pattern.finditer(body):
            matches.append((match.group(1).strip(), match.group(2)[:4]))
    for author_text, year in matches:
        surnames = _narrative_author_surnames(author_text)
        for ref in bibliography.values():
            if not ref.key or not (ref.year or "").startswith(year):
                continue
            bib_author = ref.key.split("|", 1)[0]
            for surname in surnames:
                if not surname:
                    continue
                if surname == bib_author or surname in bib_author or bib_author in surname:
                    keys.add(ref.key)
                    break
    return keys


def count_references_in_text(parsed: dict, bibliography: dict[int, ReferenceEntry]) -> int:
    """Referencias detectadas en el apartado bibliográfico (no se escanean citas en el cuerpo)."""
    return len(bibliography)


def extract_apa_citations(body: str) -> tuple[set[str], list[tuple[str, str]]]:
    from savt.citations import extract_apa_citations as _extract

    return _extract(body)


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
