from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Finding:
    module: str
    severity: str  # ok | info | warning | error
    title: str
    detail: str
    evidence: str = ""
    area: str = ""
    why: str = ""
    how_to_fix: str = ""


@dataclass
class ReferenceEntry:
    number: int
    raw: str
    key: str = ""
    title: str = ""
    doi: str = ""
    pmid: str = ""
    year: str = ""


@dataclass
class CitationContext:
    ref_number: int
    paragraph: str
    section: str = ""


@dataclass
class AuditReport:
    filename: str
    word_count: int
    page_estimate: float
    findings: list[Finding] = field(default_factory=list)
    bibliography: dict[int, ReferenceEntry] = field(default_factory=dict)
    cited_numbers: set[int] = field(default_factory=set)
    cited_keys: set[str] = field(default_factory=set)
    sections: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> int:
        penalties = {"error": 12, "warning": 5, "info": 1, "ok": 0}
        total = sum(penalties.get(f.severity, 0) for f in self.findings)
        return max(0, min(100, 100 - total))

    @property
    def status(self) -> str:
        errors = sum(1 for f in self.findings if f.severity == "error")
        warnings = sum(1 for f in self.findings if f.severity == "warning")
        if errors > 0:
            return "No conforme"
        if warnings > 3:
            return "Revisar"
        return "Conforme"
