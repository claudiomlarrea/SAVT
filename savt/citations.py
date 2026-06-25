from __future__ import annotations

import re
from dataclasses import dataclass, field

from savt.bibliography_styles import apa_citation_key, topical_match
from savt.models import Finding, ReferenceEntry

GENERIC_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "were",
    "have",
    "has",
    "como",
    "para",
    "sobre",
    "entre",
    "desde",
    "hacia",
    "pacientes",
    "estudios",
    "evidencia",
    "resultados",
}

# --- Patrones de detección (APA, Vancouver, IEEE, ISO 690, Harvard, leyes, identificadores) ---
NUMERIC_CITATION_PATTERN = re.compile(r"\((\d+(?:\s*[,\s\-–]\s*\d+)*)\)")
BRACKET_NUMERIC_CITATION = re.compile(r"\[(\d{1,3}(?:\s*[,\s\-–]\s*\d{1,3})*)\]")
SUPERSCRIPT_NUMERIC = re.compile(r"(?<!\d)(\d{1,3})(?:,\s*(\d{1,3}))*(?=\s*[.;,)\]]|$)")

APA_CITATION_PATTERN = re.compile(
    r"\(([^()]*?\d{4}[a-z]?[^()]*?)\)",
    re.IGNORECASE,
)
BRACKET_APA_CITATION_PATTERN = re.compile(
    r"\[([^[\]]*?\d{4}[a-z]?[^[\]]*?)\]",
    re.IGNORECASE,
)
HARVARD_CITATION_PATTERN = re.compile(
    r"\(([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúñ''\-\.\s&]{2,120}?\s+\d{4}[a-z]?)\)",
)
ISO690_NUMERIC = re.compile(
    r"\[\s*(\d{1,3}(?:\s*[,\s\-–]\s*\d{1,3})*)\s*\]",
)
CORPORATE_CITATION_PATTERN = re.compile(
    r"\(([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,6}),\s*(\d{4}[a-z]?)\)",
)
LAW_CITATION_PATTERN = re.compile(
    r"\b(?:Ley|Decreto|Real\s+Decreto|Resoluci[oó]n|Orden|Ley\s+Org[aá]nica)\s+"
    r"(?:n[°º.]?\s*)?[\d/\-]+(?:/\d{4})?",
    re.IGNORECASE,
)
NORM_CITATION_PATTERN = re.compile(
    r"\b(?:ISO|UNE|IEC|IEEE|NTC|NCh)\s*[-:]?\s*\d+(?:[-:]\d+)*(?:\s*\(\d{4}\))?",
    re.IGNORECASE,
)
DOI_CITATION_PATTERN = re.compile(
    r"\b(?:doi:\s*|https?://(?:dx\.)?doi\.org/)(10\.\S+)",
    re.IGNORECASE,
)
PMID_CITATION_PATTERN = re.compile(r"\bPMID:?\s*(\d{5,9})\b", re.IGNORECASE)
ISBN_CITATION_PATTERN = re.compile(r"\bISBN:?\s*([\d\-X]{10,17})\b", re.IGNORECASE)
INSTITUTIONAL_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:"
    r"un\.org|who\.int|oecd\.org|unesco\.org|cepal\.org|europa\.eu|"
    r"gob\.(?:es|mx|ar|cl|co|pe)|boe\.es|congreso\.es|wipo\.int|"
    r"worldbank\.org|imf\.org|ilo\.org|fao\.org|redalyc\.org|"
    r"dialnet\.unirioja\.es|scielo\.(?:org|br)|"
    r")[^\s\])>]+",
    re.IGNORECASE,
)
NARRATIVE_APA_PATTERN = re.compile(
    r"([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚáéíóúñ''\-\.]+(?:\s+(?:y|&)\s+[\wÁÉÍÓÚáéíóúñ''\-\.]+)+)\s*\((\d{4}[a-z]?)\)",
)
NARRATIVE_APA_ET_AL_PATTERN = re.compile(
    r"([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚáéíóúñ''\-\.\s]{2,80}?\s+et al\.)\s*\((\d{4}[a-z]?)\)",
)

STATISTICAL_CONTEXT = re.compile(
    r"(?i)(?:\bp\s*[<>=]|\bvalor\s+p\b|\bic\s*\(|\bnivel\s+de\s+significancia|\balpha\b|\bα\b|"
    r"significativo\s*\(|no\s+significativo)"
)


@dataclass
class CitationDetectionResult:
    cited_numbers: set[int] = field(default_factory=set)
    cited_keys: set[str] = field(default_factory=set)
    apa_contexts: list[tuple[str, str]] = field(default_factory=list)
    identifiers: dict[str, set[str]] = field(default_factory=dict)


def topical_score(reference: ReferenceEntry, paragraph: str, keywords: list[str]) -> float:
    ref_topical = topical_match(reference, keywords)
    para_tokens = {
        w
        for w in re.findall(r"[a-záéíóúñ]{4,}", paragraph.lower())
        if w not in GENERIC_STOPWORDS
    }
    ref_tokens = {
        w
        for w in re.findall(r"[a-záéíóúñ]{4,}", reference.raw.lower())
        if w not in GENERIC_STOPWORDS
    }
    overlap = len(para_tokens & ref_tokens) / max(len(para_tokens), 1) if para_tokens and ref_tokens else 0.0
    keyword_bonus = 0.35 if ref_topical else 0.0
    return min(1.0, overlap + keyword_bonus)


def _topic_keywords(parsed: dict) -> list[str]:
    return parsed.get("topic_keywords") or []


def is_reference_topical(reference: ReferenceEntry, keywords: list[str]) -> bool:
    return topical_match(reference, keywords)


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


def _add_numeric_chunk(
    chunk: str,
    body: str,
    start: int,
    cited: set[int],
    *,
    max_ref: int,
) -> None:
    if _is_false_positive_numeric_citation(chunk, body, start):
        return
    for part in re.split(r"[,\s\-–]+", chunk):
        if not part.isdigit():
            continue
        num = int(part)
        if 1900 <= num <= 2039:
            continue
        if 1 <= num <= max_ref:
            cited.add(num)


def _apa_inner_valid(inner: str) -> bool:
    inner = re.sub(r"\s+", " ", inner).strip()
    if re.search(r"[A-Za-zÁÉÍÓÚáéíóúñ]{3}.*,\s*\d{4}", inner):
        return True
    if re.search(r"[A-ZÁÉÍÓÚÑ]{2,}.*\d{4}", inner):
        return True
    return False


def _corporate_citation_key(author: str, year: str) -> str:
    from savt.bibliography_styles import normalize_author

    author = re.sub(r"\s+", " ", author).strip()
    token = normalize_author(author.split()[0] if author else "")
    return f"{token}|{year[:4]}" if token and year else ""


def detect_citations(body: str, *, max_ref: int = 500) -> CitationDetectionResult:
    """Detector generalizado de citas en el cuerpo del documento."""
    result = CitationDetectionResult()
    if not body:
        return result

    identifiers: dict[str, set[str]] = {
        "doi": set(),
        "pmid": set(),
        "isbn": set(),
        "law": set(),
        "norm": set(),
        "url": set(),
    }

    for pattern in (NUMERIC_CITATION_PATTERN,):
        for match in pattern.finditer(body):
            _add_numeric_chunk(match.group(1), body, match.start(), result.cited_numbers, max_ref=max_ref)

    for pattern in (BRACKET_NUMERIC_CITATION, ISO690_NUMERIC):
        for match in pattern.finditer(body):
            _add_numeric_chunk(match.group(1), body, match.start(), result.cited_numbers, max_ref=max_ref)

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if len(p.split()) > 8]
    author_year_patterns = (
        APA_CITATION_PATTERN,
        BRACKET_APA_CITATION_PATTERN,
        HARVARD_CITATION_PATTERN,
    )

    for paragraph in paragraphs:
        keys_in_paragraph: set[str] = set()
        for pattern in author_year_patterns:
            for match in pattern.finditer(paragraph):
                inner = re.sub(r"\s+", " ", match.group(1)).strip()
                if not _apa_inner_valid(inner):
                    continue
                key = apa_citation_key(inner)
                if key:
                    keys_in_paragraph.add(key)
        for match in CORPORATE_CITATION_PATTERN.finditer(paragraph):
            key = _corporate_citation_key(match.group(1), match.group(2))
            if key:
                keys_in_paragraph.add(key)
        for key in keys_in_paragraph:
            result.cited_keys.add(key)
            result.apa_contexts.append((key, paragraph))

    for match in NARRATIVE_APA_PATTERN.finditer(body):
        inner = f"{match.group(1).strip()}, {match.group(2)}"
        key = apa_citation_key(inner)
        if key:
            result.cited_keys.add(key)

    for match in NARRATIVE_APA_ET_AL_PATTERN.finditer(body):
        inner = f"{match.group(1).strip()}, {match.group(2)}"
        key = apa_citation_key(inner)
        if key:
            result.cited_keys.add(key)

    for match in LAW_CITATION_PATTERN.finditer(body):
        token = re.sub(r"\s+", " ", match.group(0)).strip().lower()
        identifiers["law"].add(token)
        result.cited_keys.add(f"law|{token[:48]}")

    for match in NORM_CITATION_PATTERN.finditer(body):
        token = match.group(0).strip().upper()
        identifiers["norm"].add(token)
        result.cited_keys.add(f"norm|{token[:32]}")

    for match in DOI_CITATION_PATTERN.finditer(body):
        doi = match.group(1).rstrip(".,;)")
        identifiers["doi"].add(doi)
        result.cited_keys.add(f"doi|{doi[:40]}")

    for match in PMID_CITATION_PATTERN.finditer(body):
        identifiers["pmid"].add(match.group(1))
        result.cited_keys.add(f"pmid|{match.group(1)}")

    for match in ISBN_CITATION_PATTERN.finditer(body):
        identifiers["isbn"].add(match.group(1))
        result.cited_keys.add(f"isbn|{match.group(1)}")

    for match in INSTITUTIONAL_URL_PATTERN.finditer(body):
        url = match.group(0).rstrip(".,;)")
        identifiers["url"].add(url)
        result.cited_keys.add(f"url|{url[:60]}")

    result.identifiers = identifiers
    return result


def extract_cited_numbers(body: str, max_ref: int = 500) -> set[int]:
    return detect_citations(body, max_ref=max_ref).cited_numbers


def extract_apa_citations(body: str) -> tuple[set[str], list[tuple[str, str]]]:
    """Compatibilidad: devuelve claves autor|año y contextos de párrafo."""
    detected = detect_citations(body, max_ref=500)
    apa_keys = {
        key
        for key in detected.cited_keys
        if "|" in key
        and not key.startswith(("law|", "norm|", "doi|", "pmid|", "isbn|", "url|"))
    }
    return apa_keys, detected.apa_contexts


def count_numeric_citation_appearances(body: str, max_ref: int = 500) -> int:
    appearances = 0
    for pattern in (NUMERIC_CITATION_PATTERN, BRACKET_NUMERIC_CITATION):
        for match in pattern.finditer(body):
            if not _is_false_positive_numeric_citation(match.group(1), body, match.start()):
                appearances += 1
    appearances += len(APA_CITATION_PATTERN.findall(body))
    appearances += len(BRACKET_APA_CITATION_PATTERN.findall(body))
    appearances += len(HARVARD_CITATION_PATTERN.findall(body))
    appearances += len(LAW_CITATION_PATTERN.findall(body))
    appearances += len(NORM_CITATION_PATTERN.findall(body))
    appearances += len(DOI_CITATION_PATTERN.findall(body))
    return appearances


def _audit_numbered_citations(parsed: dict, keywords: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    bibliography: dict[int, ReferenceEntry] = parsed["bibliography"]
    bib_nums = set(bibliography.keys())
    if not bib_nums:
        return findings

    expected = set(range(1, max(bib_nums) + 1))
    gaps = sorted(expected - bib_nums)
    if gaps:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="error",
                title="Numeración bibliográfica no consecutiva",
                detail=f"Faltan referencias en la secuencia: {gaps[:15]}",
                evidence=f"Última referencia detectada: {max(bib_nums)}",
            )
        )
    else:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="ok",
                title="Bibliografía numerada detectada",
                detail=f"Se detectaron {len(bibliography)} referencias en el apartado bibliográfico.",
            )
        )
    return findings


def _audit_apa_citations(parsed: dict, keywords: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    bibliography: dict[int, ReferenceEntry] = parsed["bibliography"]
    if bibliography:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="ok",
                title="Bibliografía APA detectada",
                detail=f"Se detectaron {len(bibliography)} referencias en el apartado bibliográfico.",
            )
        )
    return findings


def audit_citations(parsed: dict) -> list[Finding]:
    findings: list[Finding] = []
    bibliography: dict[int, ReferenceEntry] = parsed["bibliography"]
    style = parsed.get("citation_style", "numbered")
    keywords = _topic_keywords(parsed)

    if not bibliography:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="error",
                area="Bibliografía",
                title="No se detectó bibliografía",
                detail="No se encontró una sección BIBLIOGRAFÍA parseable al final del documento.",
                why="Sin bibliografía no es posible verificar trazabilidad académica.",
                how_to_fix="Agregue una sección final titulada BIBLIOGRAFÍA con referencias completas.",
            )
        )
        return findings

    if style == "apa":
        findings.extend(_audit_apa_citations(parsed, keywords))
    else:
        findings.extend(_audit_numbered_citations(parsed, keywords))

    duplicate_dois: dict[str, list[int]] = {}
    for num, ref in bibliography.items():
        if ref.doi:
            duplicate_dois.setdefault(ref.doi.lower(), []).append(num)
    dupes = {doi: nums for doi, nums in duplicate_dois.items() if len(nums) > 1}
    if dupes:
        sample = ", ".join(f"{doi} → refs {nums}" for doi, nums in list(dupes.items())[:5])
        findings.append(
            Finding(
                module="Bibliografía",
                severity="warning",
                title="DOI duplicados",
                detail="Se detectaron DOI repetidos en distintas referencias.",
                evidence=sample,
            )
        )

    if style == "numbered":
        irrelevant_refs = [
            n for n, ref in bibliography.items() if not is_reference_topical(ref, keywords)
        ]
        if irrelevant_refs and len(irrelevant_refs) > len(bibliography) * 0.15:
            pass  # Detalle en bibliography_analysis.py

    return findings
