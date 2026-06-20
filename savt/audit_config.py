from __future__ import annotations

from dataclasses import dataclass, field

from savt.institutional_profiles import InstitutionalProfile, get_profile, resolve_profile


@dataclass
class AuditConfig:
    profile_id: str = "auto"
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
    _resolved_profile_id: str | None = None

    def resolve_for_document(self, full_text: str, page_estimate: float) -> None:
        profile = resolve_profile(self.profile_id, full_text, page_estimate)
        self._resolved_profile_id = profile.id

    @property
    def profile(self) -> InstitutionalProfile:
        if self._resolved_profile_id:
            return get_profile(self._resolved_profile_id)
        return get_profile(self.profile_id if self.profile_id != "auto" else "grado_tesina")

    @property
    def effective_min_pages(self) -> int:
        return self.min_pages if self.min_pages is not None else self.profile.min_pages

    @property
    def effective_max_pages(self) -> int:
        return self.max_pages if self.max_pages is not None else self.profile.max_pages
