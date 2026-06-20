from __future__ import annotations

from dataclasses import dataclass, field

from savt.institutional_profiles import InstitutionalProfile, get_profile


@dataclass
class AuditConfig:
    profile_id: str = "grado_generico"
    verify_references_online: bool = True
    max_doi_checks: int = 200
    min_pages: int | None = None
    max_pages: int | None = None
    similarity_index: float | None = None
    plagiarism_report_text: str = ""
    check_ethics: bool = True
    check_originality: bool = True
    check_formal: bool = True
    check_content_depth: bool = True

    @property
    def profile(self) -> InstitutionalProfile:
        return get_profile(self.profile_id)

    @property
    def effective_min_pages(self) -> int:
        return self.min_pages if self.min_pages is not None else self.profile.min_pages

    @property
    def effective_max_pages(self) -> int:
        return self.max_pages if self.max_pages is not None else self.profile.max_pages
