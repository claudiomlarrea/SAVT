from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from savt import __app_name__, __version__
from savt.audit import run_audit
from savt.audit_config import AuditConfig
from savt.export_docx import build_report_docx
from savt.institutional_profiles import PROFILES, profile_options
from savt.report_builder import findings_dataframe_rows
from savt.taxonomy import AUDIT_AREAS, SEVERITY_LABELS
from savt.ui_branding import LOGO_PATH, inject_branding

st.set_page_config(
    page_title="SAVT — Auditoría de Tesis",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_branding()

SEVERITY_FILTER_OPTIONS = [
    "Errores críticos",
    "Advertencias",
    "Recomendaciones",
]


def render_header() -> None:
    logo_col, hero_col = st.columns([1, 4], vertical_alignment="center")
    with logo_col:
        st.image(LOGO_PATH, width=130)
    with hero_col:
        st.markdown(
            f"""
            <div class="savt-hero">
                <h1>SAVT</h1>
                <p class="savt-subtitle">{__app_name__} · v{__version__}</p>
                <p class="savt-desc">
                    Pre-auditoría académica integral de tesis y trabajos finales: estructura, coherencia,
                    normativa institucional, integridad, ética, profundidad y preparación para la defensa.
                    Genera observaciones y recomendaciones antes de la evaluación del jurado.
                </p>
                <p class="savt-institution">Universidad Católica de Cuyo · Observatorio de Inteligencia Artificial</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar(report=None) -> AuditConfig:
    st.sidebar.image(LOGO_PATH, width=120)
    st.sidebar.header("Configuración")

    profile_ids = [p[0] for p in profile_options()]
    profile_labels = {p[0]: p[1] for p in profile_options()}
    default_profile = st.session_state.get("profile_id", "auto")
    if default_profile not in profile_ids:
        default_profile = "auto"

    profile_id = st.sidebar.selectbox(
        "Nivel de titulación",
        options=profile_ids,
        index=profile_ids.index(default_profile),
        format_func=lambda x: profile_labels[x],
    )
    profile = PROFILES[profile_id]
    st.sidebar.caption(profile.description)

    verify_online = st.sidebar.checkbox("Verificar DOI online (Crossref)", value=True)
    max_doi = st.sidebar.slider("Máximo de DOI a verificar", 5, 200, 200)

    min_pages = st.sidebar.number_input(
        "Páginas mínimas objetivo",
        min_value=1,
        max_value=400,
        value=profile.min_pages,
    )
    max_pages = st.sidebar.number_input(
        "Páginas máximas objetivo",
        min_value=1,
        max_value=400,
        value=profile.max_pages,
    )

    st.sidebar.markdown("**Integridad académica**")
    use_similarity = st.sidebar.checkbox("Incluir índice de similitud externo", value=False)
    similarity_index = None
    plagiarism_text = ""
    if use_similarity:
        similarity_index = st.sidebar.slider(
            "Índice de similitud (Turnitin / iThenticate %)",
            0.0,
            50.0,
            0.0,
            0.5,
        )
        if similarity_index == 0.0:
            similarity_index = None
        with st.sidebar.expander("Pegar texto del reporte de similitud", expanded=False):
            plagiarism_text = st.text_area(
                "Texto del reporte",
                height=100,
                placeholder="Pegue aquí el resumen del reporte Turnitin/iThenticate…",
                label_visibility="collapsed",
            )

    st.sidebar.markdown("**Módulos de auditoría**")
    check_formal = st.sidebar.checkbox("Normativa institucional", value=True)
    check_ethics = st.sidebar.checkbox("Ética de investigación", value=True)
    check_originality = st.sidebar.checkbox("Originalidad y aporte", value=True)
    check_content = st.sidebar.checkbox("Profundidad académica", value=True)

    if report:
        with st.sidebar.expander("Datos técnicos del documento", expanded=False):
            st.write(f"Perfil: {report.metadata.get('profile_label', '—')}")
            st.write(f"Palabras (cuerpo): {report.word_count:,}")
            st.write(f"Referencias: {len(report.bibliography)}")
            st.write(f"Estilo: {report.metadata.get('citation_style', '—').upper()}")
            if report.metadata.get("file_type") == "pdf":
                st.write(f"Páginas PDF: {report.metadata.get('pdf_page_count', '—')}")
            else:
                st.write(f"Páginas est.: {report.page_estimate}")
            if report.page_estimate < min_pages or report.page_estimate > max_pages:
                st.warning(f"Extensión fuera del rango {min_pages}–{max_pages} páginas.")

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Versión {__version__}")

    return AuditConfig(
        profile_id=profile_id,
        verify_references_online=verify_online,
        max_doi_checks=max_doi,
        min_pages=int(min_pages),
        max_pages=int(max_pages),
        similarity_index=similarity_index,
        plagiarism_report_text=plagiarism_text,
        check_ethics=check_ethics,
        check_originality=check_originality,
        check_formal=check_formal,
        check_content_depth=check_content,
    )


def icon(ok: bool, partial: bool = False) -> str:
    if ok:
        return "✔"
    if partial:
        return "⚠"
    return "✖"


def render_verdict(dashboard: dict) -> None:
    st.markdown("## ICAI — Índice de Conformidad Académica Institucional")
    st.caption(
        "Mide la preparación global de la tesis para presentación: estructura, coherencia, "
        "bibliografía, citas y calidad formal. Es una guía de revisión previa a la entrega."
    )

    left, right = st.columns([1, 1.4])
    with left:
        st.markdown(f"### **{dashboard['icai']}/100**")
        st.markdown(f"**{dashboard['icai_interpretation']}**")
        st.progress(min(dashboard["icai"], 100) / 100)
        with st.expander("Escala ICAI", expanded=False):
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

    with right:
        st.markdown(f"### Estado general")
        st.markdown(f"## {dashboard['presentation_emoji']} {dashboard['readiness']}")
        st.markdown(f"**Motivo principal:** {dashboard['main_reason']}")


def render_checklist(dashboard: dict) -> None:
    from savt.chapter_reviews import CHECK_LABELS

    checklist = dashboard["checklist"]
    st.markdown("## Checklist previo a la entrega")
    st.markdown(f"**Estado:** {checklist['status']}")

    for item in checklist["items"]:
        if item["ok"]:
            mark = "✔"
        elif item.get("partial"):
            mark = "⚠"
        else:
            mark = "✖"

        st.markdown(f"{mark} **{item['label']}**")

        if not item["ok"] or item.get("partial"):
            with st.expander(f"Qué revisar en {item['label'].split(' — ')[0]}", expanded=False):
                st.write(item.get("summary", ""))
                missing = item.get("missing") or []
                if missing:
                    st.markdown("**Elementos a reforzar:**")
                    for label in missing:
                        st.markdown(f"- {CHECK_LABELS.get(label, label)}")
                if item.get("why"):
                    st.markdown(f"**Por qué importa:** {item['why']}")
                if item.get("how_to_fix"):
                    st.info(f"**Cómo corregir:** {item['how_to_fix']}")
        st.markdown("")


def render_warnings(dashboard: dict) -> None:
    warnings = dashboard.get("warnings_list") or []
    bib_details = dashboard.get("bibliography_dashboard", {}).get("details") or {}
    doi_help = bib_details.get("doi_help") or {}

    if not warnings:
        st.success("No se detectaron advertencias ni errores críticos prioritarios.")
        return

    st.markdown(f"## Advertencias detectadas ({len(warnings)})")
    for idx, item in enumerate(warnings, start=1):
        st.markdown(f"**{idx}. {item['title']}**")
        st.caption(item["gravity"])
        with st.expander("Ver detalle y cómo corregir", expanded=idx == 1):
            st.write(item["detail"])

            if "DOI inválidos" in item.get("finding_title_raw", ""):
                st.markdown(doi_help.get("invalid", ""))
                st.markdown(doi_help.get("not_resolved", ""))

            detail_items = item.get("detail_items") or []
            if detail_items:
                st.markdown("**Referencias / citas a revisar:**")
                for row in detail_items[:20]:
                    st.markdown(f"- **{row['label']}:** {row['value']}")
                    if row.get("extra"):
                        st.caption(row["extra"])

            if item.get("why"):
                st.markdown(f"**Por qué importa:** {item['why']}")
            if item.get("how_to_fix"):
                st.info(f"**Cómo corregir:** {item['how_to_fix']}")


def render_jury(dashboard: dict) -> None:
    jury = dashboard["jury"]
    st.markdown("## Evaluación orientativa por SAVT")
    st.caption(jury.get("disclaimer", ""))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Fortalezas principales**")
        for idx, item in enumerate(jury["strengths"], start=1):
            st.write(f"{idx}. {item}")
    with c2:
        st.markdown("**Debilidades principales**")
        for idx, item in enumerate(jury["weaknesses"], start=1):
            st.write(f"{idx}. {item}")
    with c3:
        st.markdown("**Probabilidad estimada de aprobación**")
        st.markdown(f"## {jury['approval_probability']}")


def render_structure(dashboard: dict) -> None:
    from savt.chapter_reviews import CHECK_LABELS

    chapter_reviews = dashboard.get("chapter_reviews") or []
    if chapter_reviews:
        st.markdown("## Revisión por capítulos")
        for review in chapter_reviews:
            if review["ok"]:
                mark = "✔"
            elif review.get("partial"):
                mark = "⚠"
            else:
                mark = "✖"
            st.markdown(f"### {mark} {review['title']}")
            if review["ok"]:
                st.caption(review.get("summary", "Apartado conforme."))
                continue
            st.write(review.get("summary", ""))
            missing = review.get("missing", []) + review.get("partial_items", [])
            if missing:
                st.markdown("**Qué falta o no está claro:**")
                for label in missing:
                    st.markdown(f"- {CHECK_LABELS.get(label, label)}")
            if review.get("why"):
                st.markdown(f"**Por qué importa:** {review['why']}")
            if review.get("how_to_fix"):
                st.info(f"**Cómo corregir:** {review['how_to_fix']}")
            st.markdown("")
        return

    structure = dashboard["structure"]
    st.markdown("## Estructura del trabajo")

    sections = [
        ("Introducción", "introduccion", ["problema", "justificación", "pregunta", "objetivos"]),
        ("Marco teórico", "marco_teorico", ["marco presente", "marco desarrollado", "marco vinculado"]),
        ("Metodología", "metodologia", ["diseño", "población", "muestra", "variables", "limitaciones"]),
        ("Resultados", "resultados", ["resultados presente", "resultados desarrollo"]),
        ("Discusión", "discusion", [
            "discusion presente",
            "discusion desarrollo",
            "interpretación",
            "confronta literatura",
            "vincula objetivos",
            "limitaciones discusion",
            "implicaciones",
        ]),
        ("Conclusiones", "conclusiones", ["responde objetivos", "responde la pregunta"]),
    ]

    for title, key, labels in sections:
        block = structure.get(key, {})
        checks = {c["label"]: c for c in block.get("checks", [])}
        st.markdown(f"**{title}**")
        if not checks:
            st.markdown(f"{icon(block.get('present', False))} {'Presente' if block.get('present') else 'No detectada claramente'}")
            continue
        st.markdown("*Tiene:*")
        for label in labels:
            check = checks.get(label, {})
            partial = check.get("partial", False)
            st.markdown(f"- {icon(check.get('ok', False), partial)} {label}")
        st.markdown("")


def render_research_question(dashboard: dict) -> None:
    block = dashboard.get("research_question", {})
    if not block.get("question"):
        return
    st.markdown("## Pregunta de investigación")
    st.markdown(f"**Pregunta detectada:** {block['question']}")
    st.markdown("**Evaluación:**")
    for check in block.get("checks", []):
        st.markdown(f"- {icon(check['ok'], check.get('partial', False))} {check['label']}")


def render_objectives(dashboard: dict) -> None:
    evaluations = dashboard.get("objectives_evaluation") or []
    if not evaluations:
        return
    st.markdown("## Coherencia objetivos → resultados → conclusiones")
    for item in evaluations:
        responded = item["status"] == "respondido"
        partial = item["status"] == "parcialmente respondido"
        label = {
            "respondido": "Respondido",
            "parcialmente respondido": "Parcialmente respondido",
            "sin evidencia clara": "Sin evidencia clara",
        }.get(item["status"], item["status"].capitalize())
        st.markdown(f"**Objetivo específico {item['number']}** — {icon(responded, partial)} {label}")
        st.caption(item["text"][:240] + ("…" if len(item["text"]) > 240 else ""))


def render_bibliography(dashboard: dict) -> None:
    bib = dashboard["bibliography_dashboard"]
    details = bib.get("details") or {}
    st.markdown("## Bibliografía")

    summary_lines = [
        f"✔ Estilo {bib['style']} correcto",
        f"✔ {bib['total_refs']} referencias",
        f"✔ {bib['citations_found']} citas encontradas",
    ]
    if bib["unmatched_citations"]:
        summary_lines.append(f"⚠ {bib['unmatched_citations']} citas no emparejadas")
    else:
        summary_lines.append("✔ Citas emparejadas con bibliografía")
    if bib["out_of_period"]:
        summary_lines.append(f"⚠ {bib['out_of_period']} referencias fuera del período metodológico")
    if bib["possibly_off_topic"]:
        summary_lines.append(
            f"⚠ {bib['possibly_off_topic']} referencias podrían no estar relacionadas con el tema"
        )
    coverage_ok = bib["coverage"] == "adecuada"
    summary_lines.append(
        f"{'✔' if coverage_ok else '⚠'} Cobertura bibliográfica {bib['coverage']}"
    )
    for line in summary_lines:
        st.markdown(line)

    unmatched = details.get("unmatched_apa") or []
    if unmatched:
        with st.expander(f"Citas no emparejadas ({len(unmatched)})", expanded=True):
            for entry in unmatched:
                cites = ", ".join(entry["citations_in_text"])
                st.markdown(f"- **En el texto:** {cites}")
                st.caption(f"Clave detectada: `{entry['key']}` — {entry['hint']}")

    out_of_period = details.get("out_of_period") or []
    if out_of_period:
        period = out_of_period[0].get("period_declared", "")
        with st.expander(f"Referencias anteriores al período {period} ({len(out_of_period)})", expanded=False):
            for entry in out_of_period[:20]:
                st.markdown(f"- **Ref. {entry['number']} ({entry['year']}):** {entry['summary']}")

    off_topic = details.get("off_topic") or []
    if off_topic:
        with st.expander(f"Referencias posiblemente ajenas al tema ({len(off_topic)})", expanded=False):
            for entry in off_topic[:20]:
                st.markdown(f"- **Ref. {entry['number']}:** {entry['summary']}")
                st.caption(entry.get("reason", ""))

    doi_invalid = details.get("doi_invalid") or []
    doi_not_resolved = details.get("doi_not_resolved") or []
    doi_network = details.get("doi_network") or []
    doi_year = details.get("doi_year_mismatch") or []
    doi_help = details.get("doi_help") or {}

    if doi_invalid or doi_not_resolved:
        with st.expander(
            f"DOI inválidos ({len(doi_invalid)}) / no resueltos ({len(doi_not_resolved)})",
            expanded=True,
        ):
            st.markdown(doi_help.get("invalid", ""))
            for entry in doi_invalid:
                st.markdown(f"- **Ref. {entry['number']}:** [{entry['doi_url']}]({entry['doi_url']})")
                st.caption(entry["message"])
            st.markdown(doi_help.get("not_resolved", ""))
            for entry in doi_not_resolved:
                st.markdown(f"- **Ref. {entry['number']}:** [{entry['doi_url']}]({entry['doi_url']})")
                st.caption(f"{entry['message']} — {entry['summary'][:100]}…")

    if doi_year:
        with st.expander(f"Año distinto al registrado en Crossref ({len(doi_year)})", expanded=False):
            st.markdown(doi_help.get("year_mismatch", ""))
            for entry in doi_year:
                st.markdown(
                    f"- **Ref. {entry['number']}:** bibliografía **{entry['year_in_bibliography']}** "
                    f"vs Crossref **{entry['year_in_crossref']}**"
                )
                st.markdown(f"  [{entry['doi_url']}]({entry['doi_url']})")
                st.caption(entry["summary"])

    if doi_network:
        with st.expander(f"DOI no verificados por red ({len(doi_network)})", expanded=False):
            st.markdown(doi_help.get("network", ""))
            for entry in doi_network:
                st.markdown(f"- **Ref. {entry['number']}:** [{entry['doi_url']}]({entry['doi_url']})")


def render_figures_tables(dashboard: dict) -> None:
    figures = dashboard.get("figures_detail") or []
    tables = dashboard.get("tables_detail") or []
    if not figures and not tables:
        return

    st.markdown("## Figuras y tablas")
    for fig in figures:
        st.markdown(f"**Figura {fig['number']}**")
        parts = []
        if not fig["has_number"]:
            parts.append("⚠ Sin número claro")
        else:
            parts.append("✔ Tiene número")
        parts.append(f"{'✔' if fig['has_title'] else '⚠'} Tiene título")
        parts.append(f"{'✔' if fig['cited_in_text'] else '⚠ No se menciona en el texto'}")
        parts.append(f"{'✔' if fig['has_source'] else '⚠ No indica fuente'}")
        st.markdown(" · ".join(parts))
        st.caption(fig["title"][:180])

    for tab in tables:
        st.markdown(f"**Tabla {tab['number']}**")
        parts = []
        parts.append(f"{'✔' if tab['has_number'] else '⚠'} Numeración")
        parts.append(f"{'✔' if tab['has_title'] else '⚠'} Título")
        parts.append(f"{'✔' if tab['has_source'] else '⚠'} Fuente")
        parts.append(f"{'✔' if tab['cited_in_text'] else '⚠'} Mención en texto")
        st.markdown(" · ".join(parts))
        st.caption(tab["title"][:180])


def render_formal(dashboard: dict) -> None:
    formal = dashboard.get("formal_dashboard") or {}
    if not formal:
        return
    st.markdown("## Normativa institucional")
    st.caption(f"Perfil: {dashboard.get('profile_label', '—')}")

    items = [
        ("Portada completa", formal.get("portada_completa")),
        ("Índice general", formal.get("indice")),
        ("Índice de figuras", formal.get("indice_figuras")),
        ("Índice de tablas", formal.get("indice_tablas")),
        ("Palabras clave", formal.get("palabras_clave")),
    ]
    for label, ok in items:
        if ok is None:
            continue
        st.markdown(f"{'✔' if ok else '⚠'} {label}")

    abstract_words = formal.get("abstract_words", 0)
    if abstract_words:
        st.markdown(f"**Resumen:** ~{abstract_words} palabras")
        preview = formal.get("abstract_text_preview", "")
        if preview:
            st.caption(preview + "…")

    ref_count = formal.get("reference_count")
    if ref_count is not None:
        st.markdown(f"**Referencias detectadas:** {ref_count}")


def render_integrity(dashboard: dict) -> None:
    integrity = dashboard.get("integrity_dashboard") or {}
    if not integrity:
        return
    st.markdown("## Integridad académica")
    st.info(integrity.get("disclaimer", ""))

    index = integrity.get("similarity_index")
    source = integrity.get("source", "—")
    if index is not None:
        st.markdown(f"**Índice de similitud externo:** {index:.1f}% (fuente: {source})")
        ai_score = integrity.get("ai_score")
        if ai_score is not None:
            st.markdown(f"**Indicador IA en reporte:** {ai_score:.1f}%")
    else:
        st.warning(
            "Sin reporte de similitud externo. SAVT solo detecta repeticiones internas; "
            "solicite escaneo Turnitin/iThenticate a su director."
        )


def render_ethics(dashboard: dict) -> None:
    ethics = dashboard.get("ethics_dashboard") or {}
    if not ethics:
        return
    st.markdown("## Ética de investigación")
    if ethics.get("is_empirical"):
        st.caption("Investigación empírica detectada — checklist ético")
    else:
        st.caption("Estudio documental o sin participantes detectados")

    checklist = ethics.get("checklist") or []
    for item in checklist:
        mark = "✔" if item.get("found") else "✖"
        st.markdown(f"{mark} {item.get('label', '')}")

    found = ethics.get("found_count", 0)
    total = ethics.get("total", 0)
    if total:
        st.progress(found / total if total else 0)
        st.caption(f"{found}/{total} elementos éticos detectados en el texto")


def render_content_depth(dashboard: dict) -> None:
    content = dashboard.get("content_dashboard") or {}
    if not content:
        return
    st.markdown("## Profundidad académica")
    cols = st.columns(3)
    with cols[0]:
        st.metric("Palabras marco teórico", content.get("marco_word_count", 0))
    with cols[1]:
        st.metric("Densidad de citas /100 pal.", content.get("citation_density_marco", 0))
    with cols[2]:
        st.metric("Marcadores críticos", content.get("critical_markers_found", 0))

    if content.get("hypothesis_detected"):
        st.markdown("✔ Hipótesis detectada")
    results = content.get("results_development")
    if results and results != "unknown":
        label = "adecuada" if results == "adequate" else "requiere refuerzo"
        st.markdown(f"**Desarrollo de resultados:** {label}")


def render_originality(dashboard: dict) -> None:
    orig = dashboard.get("originality_dashboard") or {}
    if not orig:
        return
    st.markdown("## Originalidad y aporte")
    st.caption(
        "Indicadores heurísticos — no sustituyen evaluación de originalidad por el jurado."
    )
    cols = st.columns(4)
    with cols[0]:
        st.metric("Índice proxy", f"{orig.get('score_proxy', 0)}/100")
    with cols[1]:
        st.metric("Marcadores de aporte", orig.get("contribution_markers", 0))
    with cols[2]:
        st.metric("Datos propios", orig.get("own_data_markers", 0))
    with cols[3]:
        st.metric("Nivel exigido", orig.get("level", "—"))


def render_defense_prep(dashboard: dict) -> None:
    prep = dashboard.get("defense_prep") or {}
    if not prep:
        return
    st.markdown("## Preparación para la defensa oral")
    st.caption("Preguntas probables derivadas de hallazgos y estándares de jurados")

    for idx, item in enumerate(prep.get("questions") or [], start=1):
        st.markdown(f"**{idx}. [{item.get('category', 'General')}]** {item.get('question', '')}")
        st.caption(f"Basado en: {item.get('based_on', '—')}")

    st.markdown("**Recomendaciones para la defensa:**")
    for tip in prep.get("tips") or []:
        st.markdown(f"- {tip}")


def render_findings_table(report) -> None:
    with st.expander("Detalle completo de hallazgos (filtros avanzados)", expanded=False):
        rows = findings_dataframe_rows(report)
        ok_rows = []
        for finding in report.findings:
            if finding.severity == "ok":
                from savt.report_builder import display_title
                from savt.taxonomy import enrich_finding, severity_label

                enrich_finding(finding)
                ok_rows.append(
                    {
                        "Área": finding.area or finding.module,
                        "Severidad": severity_label(finding.severity),
                        "Hallazgo": display_title(finding),
                        "Qué significa": finding.detail,
                    }
                )

        df = pd.DataFrame(rows)
        c1, c2, c3 = st.columns(3)
        with c1:
            severity_filter = st.multiselect(
                "Mostrar",
                options=SEVERITY_FILTER_OPTIONS + ["Aspectos conformes"],
                default=SEVERITY_FILTER_OPTIONS,
            )
        with c2:
            area_filter = st.multiselect(
                "Áreas a revisar",
                options=AUDIT_AREAS,
                default=AUDIT_AREAS,
            )
        with c3:
            show_ok = st.checkbox("Incluir aspectos conformes", value=False)

        if show_ok:
            df = pd.concat([df, pd.DataFrame(ok_rows)], ignore_index=True)
        filtered = df[df["Severidad"].isin(severity_filter) & df["Área"].isin(area_filter)]
        st.dataframe(filtered, use_container_width=True, hide_index=True)


def render_bibliography_table(report) -> None:
    with st.expander("Listado completo de referencias detectadas", expanded=False):
        st.caption(
            "Cada fila es una referencia que el sistema extrajo de la bibliografía de su tesis: "
            "si está citada en el texto, año, DOI y texto de la entrada."
        )
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


def main() -> None:
    render_header()
    report = st.session_state.get("report")
    config = render_sidebar(report)

    uploaded = st.file_uploader(
        "Subir tesis (.docx o .pdf)",
        type=["docx", "pdf"],
        help="Word (.docx) o PDF exportado desde Word.",
    )

    if not uploaded:
        st.info(
            "Suba un archivo .docx o .pdf para iniciar la pre-auditoría académica. "
            "Seleccione el perfil institucional en la barra lateral (UCCuyo, UNCUyo, posgrado). "
            "El informe cubre estructura, normativa, integridad, ética, profundidad y defensa oral."
        )
        return

    if st.button("Ejecutar auditoría", type="primary", use_container_width=True):
        with st.spinner("Analizando tesis…"):
            report = run_audit(
                io.BytesIO(uploaded.getvalue()),
                filename=uploaded.name,
                config=config,
            )
        st.session_state["report"] = report
        st.session_state["profile_id"] = config.profile_id
        st.rerun()

    report = st.session_state.get("report")
    if not report or report.filename != uploaded.name:
        return

    dashboard = report.metadata.get("dashboard", {})
    if not dashboard:
        st.error("Informe incompleto. Vuelva a ejecutar la auditoría.")
        return

    render_verdict(dashboard)
    st.divider()
    render_checklist(dashboard)
    st.divider()
    render_warnings(dashboard)
    st.divider()
    render_jury(dashboard)
    st.divider()
    render_formal(dashboard)
    st.divider()
    render_integrity(dashboard)
    st.divider()
    render_ethics(dashboard)
    st.divider()
    render_content_depth(dashboard)
    st.divider()
    render_originality(dashboard)
    st.divider()
    render_structure(dashboard)
    render_research_question(dashboard)
    render_objectives(dashboard)
    render_bibliography(dashboard)
    render_figures_tables(dashboard)
    st.divider()
    render_defense_prep(dashboard)
    st.divider()
    render_findings_table(report)
    render_bibliography_table(report)

    base_name = uploaded.name.rsplit(".", 1)[0]
    col_csv, col_docx = st.columns(2)

    csv = pd.DataFrame(findings_dataframe_rows(report)).to_csv(index=False).encode("utf-8")
    with col_csv:
        st.download_button(
            "Descargar informe CSV",
            data=csv,
            file_name=f"informe_savt_{base_name}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_docx:
        docx_bytes = build_report_docx(report, dashboard)
        st.download_button(
            "Descargar informe Word (.docx)",
            data=docx_bytes,
            file_name=f"informe_savt_{base_name}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
