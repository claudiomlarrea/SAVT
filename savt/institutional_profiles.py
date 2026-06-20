from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InstitutionalProfile:
    id: str
    label: str
    description: str
    min_pages: int
    max_pages: int
    abstract_min_words: int
    abstract_max_words: int
    min_references: int
    citation_style: str  # apa | numbered | any
    requires_ethics: bool
    originality_level: str  # basic | standard | strict
    institution: str = "Universal"
    keywords: tuple[str, ...] = field(default_factory=tuple)


PROFILES: dict[str, InstitutionalProfile] = {
    "auto": InstitutionalProfile(
        id="auto",
        label="Auto — detectar nivel",
        description="Infiera grado/posgrado desde portada y extensión del documento",
        min_pages=25,
        max_pages=300,
        abstract_min_words=120,
        abstract_max_words=400,
        min_references=15,
        citation_style="any",
        requires_ethics=False,
        originality_level="standard",
    ),
    "grado_tesina": InstitutionalProfile(
        id="grado_tesina",
        label="Grado — tesina / TFG / TFI",
        description="Trabajo final de grado o tesina (25–100 pp.)",
        min_pages=25,
        max_pages=100,
        abstract_min_words=120,
        abstract_max_words=350,
        min_references=15,
        citation_style="any",
        requires_ethics=False,
        originality_level="basic",
    ),
    "especializacion": InstitutionalProfile(
        id="especializacion",
        label="Especialización",
        description="Trabajo final integrador de especialización (25–60 pp.)",
        min_pages=25,
        max_pages=60,
        abstract_min_words=100,
        abstract_max_words=300,
        min_references=15,
        citation_style="any",
        requires_ethics=False,
        originality_level="basic",
    ),
    "maestria_academica": InstitutionalProfile(
        id="maestria_academica",
        label="Maestría académica",
        description="Tesis de maestría académica (50–150 pp.)",
        min_pages=50,
        max_pages=150,
        abstract_min_words=180,
        abstract_max_words=400,
        min_references=35,
        citation_style="any",
        requires_ethics=True,
        originality_level="standard",
    ),
    "maestria_profesional": InstitutionalProfile(
        id="maestria_profesional",
        label="Maestría profesional",
        description="Trabajo final integrador de maestría profesional (40–120 pp.)",
        min_pages=40,
        max_pages=120,
        abstract_min_words=150,
        abstract_max_words=350,
        min_references=25,
        citation_style="any",
        requires_ethics=True,
        originality_level="standard",
    ),
    "doctorado": InstitutionalProfile(
        id="doctorado",
        label="Doctorado",
        description="Tesis doctoral (80–300 pp.)",
        min_pages=80,
        max_pages=300,
        abstract_min_words=220,
        abstract_max_words=450,
        min_references=55,
        citation_style="any",
        requires_ethics=True,
        originality_level="strict",
    ),
}


def get_profile(profile_id: str) -> InstitutionalProfile:
    return PROFILES.get(profile_id, PROFILES["grado_tesina"])


def resolve_profile(profile_id: str, full_text: str, page_estimate: float) -> InstitutionalProfile:
    if profile_id != "auto":
        return get_profile(profile_id)
    from savt.document_sections import suggest_degree_profile

    resolved_id = suggest_degree_profile(full_text, page_estimate)
    return get_profile(resolved_id)


def profile_options() -> list[tuple[str, str]]:
    return [(p.id, p.label) for p in PROFILES.values()]
