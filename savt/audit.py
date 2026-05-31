from __future__ import annotations

from savt.bibliography_analysis import build_bibliography_details
from savt.citations import audit_citations
from savt.coherence import audit_coherence
from savt.figures import analyze_figures
from savt.models import AuditReport
from savt.objectives_coherence import audit_objectives_coherence
from savt.parser import parse_thesis_file
from savt.research_question import audit_research_question
from savt.report_builder import build_dashboard
from savt.similarity import audit_similarity
from savt.structure import audit_structure
from savt.style import audit_style
from savt.tables import analyze_tables
from savt.taxonomy import enrich_finding


def run_audit(
    source,
    filename: str = "tesis.docx",
    verify_references_online: bool = True,
    max_doi_checks: int = 25,
) -> AuditReport:
    parsed = parse_thesis_file(source, filename=filename)
    findings = []

    structure_findings, structure_dashboard = audit_structure(parsed)
    question_findings, question_dashboard = audit_research_question(parsed)
    objective_findings, objectives_evaluation = audit_objectives_coherence(parsed)
    figure_details, figure_findings = analyze_figures(parsed["body"])
    table_details, table_findings = analyze_tables(parsed["body"])

    findings.extend(audit_citations(parsed))
    findings.extend(audit_coherence(parsed))
    findings.extend(structure_findings)
    findings.extend(question_findings)
    findings.extend(objective_findings)
    findings.extend(figure_findings)
    findings.extend(table_findings)
    findings.extend(audit_style(parsed))
    findings.extend(audit_similarity(parsed))

    bib_details, bib_findings = build_bibliography_details(
        parsed,
        parsed["bibliography"],
        verify_online=verify_references_online,
        max_checks=max_doi_checks,
    )
    findings.extend(bib_findings)

    for finding in findings:
        enrich_finding(finding)

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
        },
    )

    extras = {
        "structure": structure_dashboard,
        "objectives_evaluation": objectives_evaluation,
        "research_question": question_dashboard,
        "figures_detail": figure_details,
        "tables_detail": table_details,
        "bibliography_details": bib_details,
    }
    report.metadata["dashboard"] = build_dashboard(report, parsed, extras)
    return report
