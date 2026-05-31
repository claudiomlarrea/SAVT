from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from savt import __app_name__, __version__
from savt.audit import run_audit
from savt.report_builder import findings_dataframe_rows
from savt.taxonomy import AUDIT_AREAS, SEVERITY_LABELS

st.set_page_config(
    page_title="SAVT — Auditoría de Tesis",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

SEVERITY_FILTER_OPTIONS = list(SEVERITY_LABELS.values())


def render_header() -> None:
    st.title("SAVT")
    st.caption(__app_name__)
    st.markdown(
        """
        **Auditor académico institucional** para tesistas, directores y evaluadores.
        Cada hallazgo indica *qué significa*, *por qué importa* y *cómo corregirlo*.
        """
    )


def render_sidebar() -> tuple[bool, int, int, int]:
    st.sidebar.header("Configuración")
    verify_online = st.sidebar.checkbox("Verificar DOI online (Crossref)", value=True)
    max_doi = st.sidebar.slider("Máximo de DOI a verificar", 5, 75, 25)
    min_pages = st.sidebar.number_input("Páginas mínimas objetivo", 40, 60, 50)
    max_pages = st.sidebar.number_input("Páginas máximas objetivo", 70, 200, 150)
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Versión:** {__version__}")
    return verify_online, max_doi, min_pages, max_pages


def render_check_icon(ok: bool, partial: bool = False) -> str:
    if ok:
        return "✔"
    if partial:
        return "⚠"
    return "✖"


def render_verdict(dashboard: dict) -> None:
    st.subheader("¿Mi tesis está lista para entregar?")

    c1, c2, c3 = st.columns([1.2, 1.5, 1.3])
    with c1:
        st.metric("ICAI", f"{dashboard['icai']}/100")
        st.caption(dashboard["icai_interpretation"])
    with c2:
        st.markdown(
            f"### {dashboard['presentation_emoji']} {dashboard['presentation_status']}"
        )
        st.markdown(f"**Motivo principal:** {dashboard['main_reason']}")
    with c3:
        st.metric("Errores críticos", dashboard["errors"])
        st.metric("Advertencias", dashboard["warnings"])

    st.progress(min(dashboard["icai"], 100) / 100)

    st.markdown(
        """
        | ICAI | Interpretación |
        |------|----------------|
        | 90–100 | Excelente |
        | 80–89 | Muy buena |
        | 70–79 | Apta con ajustes menores |
        | 60–69 | Requiere revisión |
        | <60 | No apta para presentación |
        """
    )


def render_checklist(dashboard: dict) -> None:
    checklist = dashboard["checklist"]
    st.subheader("Checklist previo a la entrega")
    st.markdown(f"**Estado:** {checklist['status']}")

    cols = st.columns(2)
    for idx, item in enumerate(checklist["items"]):
        col = cols[idx % 2]
        if item.get("warning") and not item["ok"]:
            icon = "⚠"
        elif item["ok"]:
            icon = "✔"
        else:
            icon = "✖"
        col.markdown(f"{icon} {item['label']}")


def render_prioritized_warnings(dashboard: dict) -> None:
    findings = [
        f
        for f in dashboard["prioritized_findings"]
        if f.severity in ("error", "warning")
    ]
    if not findings:
        st.success("No se detectaron errores críticos ni advertencias prioritarias.")
        return

    st.subheader(f"Qué corregir primero ({len(findings)} hallazgos)")
    for idx, finding in enumerate(findings[:8], start=1):
        severity = SEVERITY_LABELS.get(finding.severity, finding.severity)
        st.markdown(f"**{idx}. {finding.title}** _({severity})_")
        st.write(finding.detail)
        if finding.why:
            st.caption(f"Por qué importa: {finding.why}")
        if finding.how_to_fix:
            st.info(f"Cómo corregir: {finding.how_to_fix}")


def render_jury(dashboard: dict) -> None:
    jury = dashboard["jury"]
    st.subheader("Evaluación como jurado")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Fortalezas principales**")
        for idx, item in enumerate(jury["strengths"] or ["—"], start=1):
            st.write(f"{idx}. {item}")
    with c2:
        st.markdown("**Debilidades principales**")
        for idx, item in enumerate(jury["weaknesses"] or ["—"], start=1):
            st.write(f"{idx}. {item}")
    with c3:
        st.metric("Probabilidad estimada de aprobación", jury["approval_probability"])


def render_structure(dashboard: dict) -> None:
    structure = dashboard["structure"]
    st.subheader("Extracción estructural")

    sections = [
        ("Introducción", "introduccion"),
        ("Metodología", "metodologia"),
        ("Resultados", "resultados"),
        ("Discusión", "discusion"),
        ("Conclusiones", "conclusiones"),
    ]
    for title, key in sections:
        block = structure.get(key, {})
        checks = block.get("checks", [])
        with st.expander(title, expanded=False):
            if not checks:
                st.write(
                    f"{render_check_icon(block.get('present', False))} "
                    f"{'Sección detectada' if block.get('present') else 'Sección no detectada claramente'}"
                )
                continue
            for check in checks:
                partial = check.get("partial", False)
                st.markdown(
                    f"{render_check_icon(check['ok'], partial)} {check['label'].capitalize()}"
                )


def render_research_question(dashboard: dict) -> None:
    block = dashboard.get("research_question", {})
    if not block.get("question"):
        return
    st.subheader("Pregunta de investigación")
    st.markdown(f"**Pregunta detectada:** {block['question']}")
    for check in block.get("checks", []):
        partial = check.get("partial", False)
        st.markdown(
            f"{render_check_icon(check['ok'], partial)} {check['label']}"
        )


def render_objectives(dashboard: dict) -> None:
    evaluations = dashboard.get("objectives_evaluation") or []
    if not evaluations:
        return
    st.subheader("Coherencia objetivos → resultados → conclusiones")
    for item in evaluations:
        icon = render_check_icon(
            item["status"] == "respondido",
            partial=item["status"] == "parcialmente respondido",
        )
        st.markdown(f"**Objetivo específico {item['number']}** {icon} {item['status'].capitalize()}")
        st.caption(item["text"][:220] + ("…" if len(item["text"]) > 220 else ""))


def render_bibliography_dashboard(dashboard: dict, report) -> None:
    bib = dashboard["bibliography_dashboard"]
    st.subheader("Bibliografía")

    lines = [
        f"✔ Estilo {bib['style']} detectado",
        f"✔ {bib['total_refs']} referencias",
        f"✔ {bib['citations_found']} citas encontradas en el texto",
    ]
    if bib["unmatched_citations"]:
        lines.append(f"⚠ {bib['unmatched_citations']} citas no emparejadas")
    else:
        lines.append("✔ Citas emparejadas con bibliografía")
    if bib["out_of_period"]:
        lines.append(f"⚠ {bib['out_of_period']} referencias anteriores al período metodológico")
    if bib["possibly_off_topic"]:
        lines.append(
            f"⚠ {bib['possibly_off_topic']} referencias podrían no relacionarse con el tema central"
        )
    coverage_icon = "✔" if bib["coverage"] == "adecuada" else "⚠"
    lines.append(f"{coverage_icon} Cobertura bibliográfica {bib['coverage']}")

    for line in lines:
        st.markdown(line)


def render_figures_tables(dashboard: dict) -> None:
    figures = dashboard.get("figures_detail") or []
    tables = dashboard.get("tables_detail") or []
    if not figures and not tables:
        return

    st.subheader("Figuras y tablas")
    if figures:
        st.markdown("**Figuras**")
        for fig in figures:
            st.markdown(f"**Figura {fig['number']}**")
            st.markdown(
                f"{render_check_icon(fig['has_number'])} Tiene número · "
                f"{render_check_icon(fig['has_title'])} Tiene título · "
                f"{render_check_icon(fig['cited_in_text'])} Citada en el texto · "
                f"{render_check_icon(fig['has_source'])} Tiene fuente"
            )
            st.caption(fig["title"][:180])
    if tables:
        st.markdown("**Tablas**")
        for tab in tables:
            st.markdown(f"**Tabla {tab['number']}**")
            st.markdown(
                f"{render_check_icon(tab['has_number'])} Tiene número · "
                f"{render_check_icon(tab['has_title'])} Tiene título · "
                f"{render_check_icon(tab['cited_in_text'])} Mencionada en el texto · "
                f"{render_check_icon(tab['has_source'])} Tiene fuente"
            )
            st.caption(tab["title"][:180])


def render_findings_table(report) -> None:
    st.subheader("Detalle de hallazgos")
    rows = findings_dataframe_rows(report)
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No se generaron hallazgos.")
        return

    c1, c2 = st.columns(2)
    with c1:
        severity_filter = st.multiselect(
            "Mostrar",
            options=SEVERITY_FILTER_OPTIONS,
            default=SEVERITY_FILTER_OPTIONS,
        )
    with c2:
        area_filter = st.multiselect(
            "Áreas a revisar",
            options=AUDIT_AREAS,
            default=AUDIT_AREAS,
        )

    filtered = df[df["Severidad"].isin(severity_filter) & df["Área"].isin(area_filter)]
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    for area in area_filter:
        subset = filtered[filtered["Área"] == area]
        if subset.empty:
            continue
        with st.expander(f"{area} ({len(subset)} hallazgos)", expanded=False):
            for _, row in subset.iterrows():
                st.markdown(f"**{row['Hallazgo']}** — _{row['Severidad']}_")
                st.write(row["Qué significa"])
                if row["Por qué importa"]:
                    st.caption(f"Por qué importa: {row['Por qué importa']}")
                if row["Cómo corregir"]:
                    st.info(f"Cómo corregir: {row['Cómo corregir']}")
                if row["Evidencia"]:
                    st.code(row["Evidencia"])


def render_bibliography_table(report) -> None:
    with st.expander("Bibliografía parseada (detalle técnico)", expanded=False):
        if not report.bibliography:
            st.warning("No se detectaron referencias.")
            return
        rows = []
        style = report.metadata.get("citation_style", "numbered")
        for num in sorted(report.bibliography):
            ref = report.bibliography[num]
            if style == "apa":
                cited = "Sí" if ref.key in report.cited_keys else "Parcial/No"
            else:
                cited = "Sí" if num in report.cited_numbers else "No"
            rows.append(
                {
                    "N°": num,
                    "Citada": cited,
                    "Año": ref.year,
                    "DOI": ref.doi,
                    "Referencia": ref.raw[:220] + ("…" if len(ref.raw) > 220 else ""),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_summary_meta(report, min_pages: int, max_pages: int) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Palabras (cuerpo)", f"{report.word_count:,}")
    c2.metric("Referencias", len(report.bibliography))
    c3.metric("Estilo citación", report.metadata.get("citation_style", "—").upper())
    if report.metadata.get("file_type") == "pdf":
        c4.metric("Páginas PDF", report.metadata.get("pdf_page_count", "—"))
    else:
        c4.metric("Páginas est.", f"{report.page_estimate}")

    if report.page_estimate < min_pages or report.page_estimate > max_pages:
        st.warning(
            f"Extensión estimada ({report.page_estimate} páginas) fuera del rango "
            f"configurado ({min_pages}–{max_pages}). Confirmar en el PDF final."
        )


def main() -> None:
    render_header()
    verify_online, max_doi, min_pages, max_pages = render_sidebar()

    uploaded = st.file_uploader(
        "Subir tesis (.docx o .pdf)",
        type=["docx", "pdf"],
        help="Word (.docx) o PDF exportado desde Word.",
    )

    if not uploaded:
        st.info("Suba un archivo .docx o .pdf para iniciar la auditoría académica.")
        st.markdown(
            """
            ### Qué evalúa SAVT
            - Estructura académica (introducción, metodología, resultados, discusión, conclusiones)
            - Coherencia pregunta → objetivos → resultados → conclusiones
            - Bibliografía, citas, figuras y tablas
            - Redacción, extensión y checklist previo a la entrega
            - Evaluación orientada a tesista, director y jurado
            """
        )
        return

    if st.button("Ejecutar auditoría", type="primary", use_container_width=True):
        with st.spinner("Analizando tesis…"):
            report = run_audit(
                io.BytesIO(uploaded.getvalue()),
                filename=uploaded.name,
                verify_references_online=verify_online,
                max_doi_checks=max_doi,
            )
        st.session_state["report"] = report

    report = st.session_state.get("report")
    if not report or report.filename != uploaded.name:
        return

    dashboard = report.metadata.get("dashboard", {})
    render_verdict(dashboard)
    render_summary_meta(report, min_pages, max_pages)

    st.markdown("---")
    render_checklist(dashboard)
    st.markdown("---")
    render_prioritized_warnings(dashboard)
    st.markdown("---")
    render_jury(dashboard)
    st.markdown("---")
    render_structure(dashboard)
    render_research_question(dashboard)
    render_objectives(dashboard)
    render_bibliography_dashboard(dashboard, report)
    render_figures_tables(dashboard)
    st.markdown("---")
    render_findings_table(report)
    render_bibliography_table(report)

    csv = pd.DataFrame(findings_dataframe_rows(report)).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Descargar informe CSV",
        data=csv,
        file_name=f"informe_savt_{uploaded.name.rsplit('.', 1)[0]}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
