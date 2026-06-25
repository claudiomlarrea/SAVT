from __future__ import annotations

from typing import Callable, Optional

from savt.audit_config import AuditConfig
from savt.bibliography_analysis import build_bibliography_details
from savt.citations import audit_citations
from savt.coherence import audit_coherence
from savt.content_quality import audit_content_quality
from savt.ethics import audit_ethics
from savt.figures import analyze_figures
from savt.formal_requirements import run_formal_audit
from savt.integrity import audit_integrity
from savt.models import AuditReport
from savt.objectives_coherence import audit_objectives_coherence
from savt.originality import audit_originality
from savt.parser import parse_thesis_file
from savt.research_question import audit_research_question
from savt.report_builder import build_dashboard
from savt.similarity import audit_similarity
from savt.structure import audit_structure
from savt.style import audit_style
from savt.tables import analyze_tables
from savt.taxonomy import enrich_finding

AuditProgressCallback = Callable[[str, str, float, Optional[dict]], None]


def _emit_progress(
    callback: AuditProgressCallback | None,
    phase: str,
    detail: str,
    fraction: float,
    payload: Optional[dict] = None,
) -> None:
    if callback:
        callback(phase, detail, fraction, payload)


def run_audit(
    source,
    filename: str = "tesis.docx",
    verify_references_online: bool = True,
    max_doi_checks: int = 25,
    config: AuditConfig | None = None,
    on_progress: Optional[AuditProgressCallback] = None,
) -> AuditReport:
    if config is None:
        config = AuditConfig(
            verify_references_online=verify_references_online,
            max_doi_checks=max_doi_checks,
        )
    else:
        config.verify_references_online = verify_references_online
        config.max_doi_checks = max_doi_checks

    parsed = parse_thesis_file(source, filename=filename)
    config.resolve_for_document(parsed.get("full_text", ""), parsed.get("page_estimate", 0))

    pipeline_steps = parsed.get("pipeline") or []
    for idx, step in enumerate(pipeline_steps):
        fraction = 0.02 + (idx + 1) * 0.06
        payload: dict | None = None
        if step.get("id") == "sections" and step.get("details", {}).get("sections"):
            payload = {"detected_sections": step["details"]["sections"]}
        _emit_progress(
            on_progress,
            step.get("title", "Procesando documento"),
            step.get("summary", ""),
            fraction,
            payload,
        )

    from savt.section_audit import detect_document_sections

    detected_sections = detect_document_sections(parsed)
    _emit_progress(
        on_progress,
        "Detección de apartados",
        f"{len(detected_sections)} apartados identificados en el documento",
        0.08,
        {"detected_sections": detected_sections},
    )

    findings = []

    structure_findings, structure_dashboard = audit_structure(parsed)
    _emit_progress(
        on_progress,
        "Estructura",
        "Revisando introducción, marco, metodología, resultados, discusión y conclusiones",
        0.22,
    )
    question_findings, question_dashboard = audit_research_question(parsed)
    objective_findings, objectives_evaluation = audit_objectives_coherence(parsed)
    figure_details, figure_findings = analyze_figures(parsed["body"])
    table_details, table_findings = analyze_tables(parsed["body"])

    formal_findings, formal_dashboard = run_formal_audit(parsed, config)
    integrity_findings, integrity_dashboard = audit_integrity(config)
    ethics_findings, ethics_dashboard = audit_ethics(parsed, config)
    content_findings, content_dashboard = audit_content_quality(parsed, config)
    _emit_progress(
        on_progress,
        "Profundidad académica",
        "Calculando palabras, citas y profundidad por apartado",
        0.42,
        {"detected_sections": detected_sections},
    )
    originality_findings, originality_dashboard = audit_originality(parsed, config)

    findings.extend(audit_citations(parsed))
    findings.extend(audit_coherence(parsed))
    findings.extend(structure_findings)
    findings.extend(question_findings)
    findings.extend(objective_findings)
    findings.extend(figure_findings)
    findings.extend(table_findings)
    findings.extend(formal_findings)
    findings.extend(integrity_findings)
    findings.extend(ethics_findings)
    findings.extend(content_findings)
    findings.extend(originality_findings)
    findings.extend(audit_style(parsed, config))
    findings.extend(audit_similarity(parsed))

    _emit_progress(
        on_progress,
        "Bibliografía y citas",
        "Verificando correspondencia citas ↔ referencias",
        0.62,
    )
    bib_details, bib_findings = build_bibliography_details(
        parsed,
        parsed["bibliography"],
        verify_online=config.verify_references_online,
        max_checks=config.max_doi_checks,
    )
    findings.extend(bib_findings)

    from savt.section_audit import tag_findings_with_sections

    for finding in findings:
        enrich_finding(finding)
    tag_findings_with_sections(
        AuditReport(filename=filename, word_count=0, page_estimate=0, findings=findings)
    )

    _emit_progress(on_progress, "Informe final", "Consolidando resultados y checklist", 0.88)

    report = AuditReport(
        filename=filename,
        word_count=parsed["word_count"],
        page_estimate=parsed["page_estimate"],
        findings=findings,
        bibliography=parsed["bibliography"],
        cited_numbers=parsed["cited_numbers"],
        cited_keys=parsed.get("cited_keys", set()),
        sections=parsed["sections"],
        metadata={
            "research_questions": parsed["research_questions"],
            "objectives": parsed["objectives"],
            "conclusions_preview": parsed["conclusions"][:500],
            "page_estimate_body_only": parsed.get("page_estimate_body_only"),
            "bibliography_word_count": parsed.get("bibliography_word_count", 0),
            "citation_style": parsed.get("citation_style"),
            "file_type": parsed.get("file_type"),
            "pdf_page_count": parsed.get("pdf_page_count"),
            "profile_id": config._resolved_profile_id or config.profile_id,
            "profile_label": config.profile.label,
            "document_title": parsed.get("document_title", ""),
            "structure_source": parsed.get("structure_source"),
            "pipeline": parsed.get("pipeline", []),
        },
    )

    extras = {
        "structure": structure_dashboard,
        "objectives_evaluation": objectives_evaluation,
        "research_question": question_dashboard,
        "figures_detail": figure_details,
        "tables_detail": table_details,
        "bibliography_details": bib_details,
        "formal_dashboard": formal_dashboard,
        "integrity_dashboard": integrity_dashboard,
        "ethics_dashboard": ethics_dashboard,
        "content_dashboard": content_dashboard,
        "originality_dashboard": originality_dashboard,
        "config": config,
        "detected_sections": detected_sections,
    }
    report.metadata["dashboard"] = build_dashboard(report, parsed, extras)
    _emit_progress(
        on_progress,
        "Completado",
        f"Auditoría finalizada — ICAI {report.score}/100",
        1.0,
        {"detected_sections": detected_sections, "section_audits": report.metadata["dashboard"].get("section_audits")},
    )
    return report
