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
    institution: str
    keywords: tuple[str, ...] = field(default_factory=tuple)


PROFILES: dict[str, InstitutionalProfile] = {
    "grado_generico": InstitutionalProfile(
        id="grado_generico",
        label="Grado — genérico",
        description="Tesina o trabajo final de grado (referencia general)",
        min_pages=30,
        max_pages=100,
        abstract_min_words=150,
        abstract_max_words=350,
        min_references=15,
        citation_style="any",
        requires_ethics=False,
        originality_level="basic",
        institution="Genérico",
    ),
    "uccuyo_tesina": InstitutionalProfile(
        id="uccuyo_tesina",
        label="UCCuyo — Tesina de grado",
        description="Tesina de licenciatura (30–80 pp., APA, resumen ≤350 palabras)",
        min_pages=30,
        max_pages=80,
        abstract_min_words=150,
        abstract_max_words=350,
        min_references=20,
        citation_style="apa",
        requires_ethics=False,
        originality_level="basic",
        institution="Universidad Católica de Cuyo",
        keywords=("uccuyo", "católica de cuyo", "catolica de cuyo"),
    ),
    "uncuyo_tesina": InstitutionalProfile(
        id="uncuyo_tesina",
        label="UNCuyo — Tesina / TFG",
        description="Trabajo final UNCuyo Fac. Educación y afines (30–50 pp.)",
        min_pages=30,
        max_pages=50,
        abstract_min_words=150,
        abstract_max_words=350,
        min_references=20,
        citation_style="apa",
        requires_ethics=False,
        originality_level="basic",
        institution="Universidad Nacional de Cuyo",
        keywords=("uncuyo", "nacional de cuyo"),
    ),
    "maestria_academica": InstitutionalProfile(
        id="maestria_academica",
        label="Maestría académica",
        description="Tesis de maestría académica (CONEAU RM 160/2011)",
        min_pages=50,
        max_pages=120,
        abstract_min_words=200,
        abstract_max_words=350,
        min_references=40,
        citation_style="apa",
        requires_ethics=True,
        originality_level="standard",
        institution="Posgrado",
    ),
    "maestria_profesional": InstitutionalProfile(
        id="maestria_profesional",
        label="Maestría profesional",
        description="Trabajo final integrador de maestría profesional",
        min_pages=40,
        max_pages=100,
        abstract_min_words=150,
        abstract_max_words=350,
        min_references=25,
        citation_style="any",
        requires_ethics=True,
        originality_level="standard",
        institution="Posgrado",
    ),
    "doctorado": InstitutionalProfile(
        id="doctorado",
        label="Doctorado",
        description="Tesis doctoral — excelencia, originalidad y aporte (CONEAU)",
        min_pages=80,
        max_pages=250,
        abstract_min_words=250,
        abstract_max_words=400,
        min_references=60,
        citation_style="apa",
        requires_ethics=True,
        originality_level="strict",
        institution="Posgrado",
    ),
    "especializacion": InstitutionalProfile(
        id="especializacion",
        label="Especialización",
        description="Trabajo final integrador de especialización",
        min_pages=25,
        max_pages=60,
        abstract_min_words=100,
        abstract_max_words=300,
        min_references=15,
        citation_style="any",
        requires_ethics=False,
        originality_level="basic",
        institution="Posgrado",
    ),
}


def get_profile(profile_id: str) -> InstitutionalProfile:
    return PROFILES.get(profile_id, PROFILES["grado_generico"])


def profile_options() -> list[tuple[str, str]]:
    return [(p.id, p.label) for p in PROFILES.values()]
