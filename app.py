from __future__ import annotations

import io
import sys

import streamlit as st

st.set_page_config(
    page_title="SAVT — Auditoría de Tesis",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _lazy_ui():
    from savt.ui_branding import LOGO_PATH, inject_branding
    from savt.ui_labels import conformance_badge, conformance_label, readiness_conformance_badge

    inject_branding()
    return LOGO_PATH, conformance_badge, conformance_label, readiness_conformance_badge


LOGO_PATH = None
conformance_badge = None
conformance_label = None
readiness_conformance_badge = None

SEVERITY_FILTER_OPTIONS = [
    "Errores críticos",
    "Advertencias",
    "Recomendaciones",
]


def render_header() -> None:
    from savt import __app_name__, __version__

    logo_col, hero_col = st.columns([1, 4])
    with logo_col:
        if LOGO_PATH and LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=130)
    with hero_col:
        st.markdown(
            f"""
            <div class="savt-hero">
                <h1>SAVT</h1>
                <p class="savt-subtitle">{__app_name__} · v{__version__}</p>
                <p class="savt-desc">
                    Pre-auditoría académica integral de tesis y trabajos finales: estructura, coherencia,
                    normativa institucional, integridad, ética y profundidad.
                    Genera observaciones y recomendaciones antes de la evaluación del jurado.
                </p>
                <p class="savt-institution">Universidad Católica de Cuyo · Observatorio de Inteligencia Artificial</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar(report=None) -> "AuditConfig":
    from savt import __version__
    from savt.audit_config import AuditConfig
    from savt.institutional_profiles import PROFILES, profile_options

    if LOGO_PATH and LOGO_PATH.exists():
        st.sidebar.image(str(LOGO_PATH), width=120)
    st.sidebar.header("Configuración")

    profile_ids = [p[0] for p in profile_options()]
    profile_labels = {p[0]: p[1] for p in profile_options()}
    # Streamlit Cloud puede reciclar session_state con ids viejos del sidebar.
    default_profile = st.session_state.get("profile_id", "auto")
    if default_profile not in profile_ids:
        default_profile = "auto"
        st.session_state["profile_id"] = default_profile
    selected_index = profile_ids.index(default_profile) if default_profile in profile_ids else 0

    profile_id = st.sidebar.selectbox(
        "Nivel de titulación",
        options=profile_ids,
        index=selected_index,
        format_func=lambda x: profile_labels[x],
    )
    profile = PROFILES[profile_id]
    st.sidebar.caption(profile.description)

    verify_online = st.sidebar.checkbox("Verificar DOI online (Crossref)", value=True)
    max_doi = st.sidebar.slider("Máximo de DOI a verificar", 5, 200, 50)

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
    st.sidebar.caption(f"Versión {__version__} · Python {sys.version.split()[0]}")

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


def render_detected_sections(dashboard: dict) -> None:
    """Apartados identificados automáticamente en el documento cargado."""
    detected = dashboard.get("detected_sections") or []
    st.markdown("## Apartados detectados en el documento")
    st.caption(
        "SAVT reconoce primero la estructura real del archivo (encabezados, capítulos o secciones "
        "canónicas) y luego audita cada bloque por separado."
    )
    if not detected:
        st.warning("No se identificaron apartados canónicos con contenido suficiente.")
        return

    rows = [
        {
            "N°": item.get("order", idx),
            "Apartado canónico": item.get("title", "—"),
            "Detectado como": item.get("detected_as", "—"),
            "Palabras": item.get("words", 0),
            "% del cuerpo": item.get("percent_label", "—"),
        }
        for idx, item in enumerate(detected, start=1)
    ]
    st.dataframe(rows, hide_index=True)
    total_words = sum(item.get("words", 0) for item in detected)
    st.caption(f"Total clasificado en apartados: **{total_words:,}** palabras en **{len(detected)}** bloques.")


def render_technical_section_detail(dashboard: dict) -> None:
    """Métricas por apartado y cuadre de citas — colapsado para no duplicar el informe principal."""
    from savt.section_audit import section_audit_summary_rows

    section_audits = dashboard.get("section_audits") or []
    reconciliation = dashboard.get("citation_reconciliation") or {}
    if not section_audits and not reconciliation.get("reconciliation_rows"):
        return

    with st.expander("Detalle técnico: métricas por apartado y cuadre de citas", expanded=False):
        st.caption(
            "Vista analítica para revisión avanzada. Las observaciones accionables están en "
            "«Apartados con observaciones»; el checklist resume el estado de cada capítulo."
        )
        if section_audits:
            st.dataframe(section_audit_summary_rows(section_audits), hide_index=True)
        recon_rows = reconciliation.get("reconciliation_rows") or []
        if recon_rows:
            st.markdown("**Cuadre de citas y referencias**")
            st.dataframe(recon_rows, hide_index=True)
            for note in reconciliation.get("notes") or []:
                if "Coincide" in note:
                    st.caption(f"✓ {note}")
                elif "Diferencia" in note or "Alerta" in note:
                    st.warning(note)
                else:
                    st.caption(note)


def render_verdict(dashboard: dict) -> None:
    st.markdown("## Resultado general (ICAI)")
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
        st.markdown("### Estado general")
        st.markdown(
            f"## {readiness_conformance_badge(dashboard['readiness'])}",
            unsafe_allow_html=True,
        )
        st.markdown(f"**{dashboard['readiness']}**")
        st.markdown(f"**Motivo principal:** {dashboard['main_reason']}")


def render_checklist(dashboard: dict) -> None:
    checklist = dashboard["checklist"]
    pending_count = sum(1 for item in checklist["items"] if not item["ok"])

    st.markdown("## Checklist de presentación")
    st.caption("Resumen ejecutivo por capítulo. El detalle accionable está en «Apartados con observaciones».")
    st.markdown(f"**Estado:** {checklist['status']}")

    for item in checklist["items"]:
        ok = item["ok"]
        partial = item.get("partial", False)
        st.markdown(
            f"{conformance_badge(ok, partial)} — {item['label']}",
            unsafe_allow_html=True,
        )

    if pending_count:
        st.caption(
            "El detalle de qué falta, por qué importa y cómo corregir figura en "
            "**Apartados con observaciones** (sección siguiente)."
        )


def render_warnings(dashboard: dict) -> None:
    warnings = dashboard.get("warnings_list") or []
    bib_details = dashboard.get("bibliography_dashboard", {}).get("details") or {}
    doi_help = bib_details.get("doi_help") or {}

    if not warnings:
        st.success("No se detectaron advertencias ni errores críticos prioritarios.")
        return

    st.caption(
        "Las páginas indicadas son estimadas a partir del cuerpo del documento "
        "(precisas en PDF; aproximadas en Word según extensión total)."
    )
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
                heading = "**Párrafos / citas / referencias a revisar:**"
                if "duplicados" in item.get("finding_title_raw", "").lower():
                    heading = "**Párrafos duplicados (página estimada):**"
                elif "Citas APA" in item.get("finding_title_raw", ""):
                    heading = "**Citas en el texto (página estimada):**"
                elif "ajenas al tema" in item.get("finding_title_raw", ""):
                    heading = "**Referencias y páginas donde se citan:**"
                elif "Año bibliográfico" in item.get("finding_title_raw", ""):
                    heading = "**Referencias con año discordante (páginas de cita):**"
                st.markdown(heading)
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


def render_apartados_con_observaciones(dashboard: dict) -> None:
    from savt.chapter_reviews import CHECK_LABELS

    chapter_reviews = dashboard.get("chapter_reviews") or []
    pending = [review for review in chapter_reviews if not review.get("ok")]

    st.markdown("## Apartados con observaciones")
    st.caption(
        "Orientación detallada solo para apartados parcialmente conformes o no conformes. "
        "Los apartados conformes no se listan aquí."
    )

    if not pending:
        st.success("Todos los apartados evaluados cumplen los criterios detectados automáticamente.")
        return

    for review in pending:
        partial = review.get("partial", False)
        status = conformance_label(False, partial)
        st.markdown(f"### {status} — {review['title']}")
        if review.get("summary"):
            st.write(review["summary"])
        missing = (review.get("missing") or []) + (review.get("partial_items") or [])
        if missing:
            st.markdown("**Qué falta o no está claro:**")
            for label in missing:
                st.markdown(f"- {CHECK_LABELS.get(label, label)}")
        if review.get("why"):
            st.markdown(f"**Por qué importa:** {review['why']}")
        if review.get("how_to_fix"):
            st.info(f"**Cómo corregir:** {review['how_to_fix']}")
        st.markdown("")


def render_bibliography(dashboard: dict) -> None:
    bib = dashboard["bibliography_dashboard"]
    details = bib.get("details") or {}
    st.markdown("## Bibliografía y citación")

    summary_lines = [
        f"{conformance_badge(True)} — Estilo {bib['style']} detectado",
        f"{conformance_badge(True)} — {bib['total_refs']} referencias",
        f"{conformance_badge(True)} — {bib['citations_found']} citas encontradas",
    ]
    if bib["unmatched_citations"]:
        summary_lines.append(
            f"{conformance_badge(False, True)} — {bib['unmatched_citations']} citas no emparejadas"
        )
    else:
        summary_lines.append(f"{conformance_badge(True)} — Citas emparejadas con bibliografía")
    if bib["out_of_period"]:
        summary_lines.append(
            f"{conformance_badge(False, True)} — {bib['out_of_period']} referencias fuera del período metodológico"
        )
    if bib["possibly_off_topic"]:
        summary_lines.append(
            f"{conformance_badge(False, True)} — "
            f"{bib['possibly_off_topic']} referencias podrían no estar relacionadas con el tema"
        )
    coverage_ok = bib["coverage"] == "adecuada"
    summary_lines.append(
        f"{conformance_badge(coverage_ok, not coverage_ok and bib['coverage'] != '—')} — "
        f"Cobertura bibliográfica {bib['coverage']}"
    )
    for line in summary_lines:
        st.markdown(line, unsafe_allow_html=True)

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

    st.markdown("### Figuras y tablas")
    for fig in figures:
        st.markdown(f"**Figura {fig['number']}**")
        parts = []
        parts.append(
            f"{conformance_badge(fig['has_number'])} — "
            f"{'Tiene número' if fig['has_number'] else 'Sin número claro'}"
        )
        parts.append(f"{conformance_badge(fig['has_title'])} — Tiene título")
        parts.append(
            f"{conformance_badge(fig['cited_in_text'], not fig['cited_in_text'])} — "
            f"{'Citada en el texto' if fig['cited_in_text'] else 'No se menciona en el texto'}"
        )
        parts.append(
            f"{conformance_badge(fig['has_source'], not fig['has_source'])} — Fuente indicada"
        )
        st.markdown(" · ".join(parts), unsafe_allow_html=True)
        st.caption(fig["title"][:180])

    for tab in tables:
        st.markdown(f"**Tabla {tab['number']}**")
        parts = []
        parts.append(f"{conformance_badge(tab['has_number'])} — Numeración")
        parts.append(f"{conformance_badge(tab['has_title'])} — Título")
        parts.append(f"{conformance_badge(tab['has_source'])} — Fuente")
        parts.append(
            f"{conformance_badge(tab['cited_in_text'], not tab['cited_in_text'])} — "
            f"{'Mención en texto' if tab['cited_in_text'] else 'Sin mención en texto'}"
        )
        st.markdown(" · ".join(parts), unsafe_allow_html=True)
        st.caption(tab["title"][:180])


def render_formal(dashboard: dict) -> None:
    formal = dashboard.get("formal_dashboard") or {}
    if not formal:
        return
    st.caption(f"Perfil normativo: {dashboard.get('profile_label', '—')}")

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
        st.markdown(
            f"{conformance_badge(bool(ok), ok is False)} — {label}",
            unsafe_allow_html=True,
        )

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
        st.markdown(
            f"{conformance_badge(bool(item.get('found')))} — {item.get('label', '')}",
            unsafe_allow_html=True,
        )

    found = ethics.get("found_count", 0)
    total = ethics.get("total", 0)
    if total:
        st.progress(found / total if total else 0)
        st.caption(f"{found}/{total} elementos éticos detectados en el texto")


def render_document_data(dashboard: dict, report) -> None:
    content = dashboard.get("content_dashboard") or {}
    formal = dashboard.get("formal_dashboard") or {}
    st.markdown("## Datos del documento")
    st.caption(f"Perfil: {dashboard.get('profile_label', '—')}")

    meta_cols = st.columns(4)
    with meta_cols[0]:
        st.metric("Palabras (cuerpo)", f"{report.word_count:,}")
    with meta_cols[1]:
        st.metric("Referencias", len(report.bibliography))
    with meta_cols[2]:
        pages = report.metadata.get("pdf_page_count") or report.page_estimate
        st.metric("Páginas", pages)
    with meta_cols[3]:
        st.metric("Estilo de citación", report.metadata.get("citation_style", "—").upper())

    help_text = content.get("indicator_help") or {}
    if content.get("bibliography_words"):
        st.caption(f"Bibliografía: {content['bibliography_words']:,} palabras.")

    sections = content.get("sections") or dashboard.get("detected_sections") or []
    if sections:
        st.markdown("### Estructura del documento")
        st.caption(help_text.get("sections", ""))
        rows = [
            {
                "Apartado": item.get("title", "—"),
                "Palabras": item.get("words", 0),
                "% del total": item.get("percent_label", "—"),
            }
            for item in sections
        ]
        st.dataframe(rows, hide_index=True)

    if formal:
        with st.expander("Normativa formal detectada", expanded=False):
            render_formal(dashboard)


def render_academic_depth(dashboard: dict) -> None:
    content = dashboard.get("content_dashboard") or {}
    if not content:
        return
    st.markdown("## Profundidad académica")
    help_text = content.get("indicator_help") or {}
    st.caption(
        "Indicadores cuantitativos por apartado (extensión, citas, marcadores). "
        "El estado conforme/no conforme figura en el checklist y en «Apartados con observaciones»."
    )

    section_depth = content.get("section_depth") or []
    if section_depth:
        rows = []
        for item in section_depth:
            if item.get("depth_status") == "missing" and item.get("words", 0) <= 0:
                continue
            result_markers = item.get("result_markers", 0)
            rows.append(
                {
                    "Apartado": item.get("title", "—"),
                    "Palabras": item.get("words", 0),
                    "Citas": item.get("citation_count", 0),
                    "Marcadores críticos": item.get("critical_markers", 0),
                    "Ind. hallazgos": result_markers if result_markers else "—",
                    "Índice profundidad": item.get("depth_label", "—"),
                }
            )
        st.dataframe(rows, hide_index=True)

    st.markdown("**Indicadores transversales**")
    if content.get("hypothesis_detected"):
        st.markdown(
            f"{conformance_badge(True)} — Hipótesis detectada",
            unsafe_allow_html=True,
        )
    results = content.get("results_development")
    if results and results != "unknown":
        adequate = results == "adequate"
        label = "adecuada" if adequate else "requiere refuerzo"
        st.markdown(
            f"{conformance_badge(adequate, not adequate)} — Desarrollo de resultados: {label}",
            unsafe_allow_html=True,
        )


def render_content_depth(dashboard: dict) -> None:
    """Compatibilidad: delega en profundidad académica."""
    render_academic_depth(dashboard)


def render_originality(dashboard: dict) -> None:
    orig = dashboard.get("originality_dashboard") or {}
    if not orig:
        return
    st.markdown("## Originalidad y aporte")
    st.caption(
        "Indicadores heurísticos — no sustituyen evaluación de originalidad por el jurado."
    )
    help_text = orig.get("indicator_help") or {}
    cols = st.columns(4)
    with cols[0]:
        st.metric("Índice proxy", f"{orig.get('score_proxy', 0)}/100")
        st.caption(help_text.get("score_proxy", ""))
    with cols[1]:
        st.metric("Marcadores de aporte", orig.get("contribution_markers", 0))
        st.caption(help_text.get("contribution_markers", ""))
    with cols[2]:
        st.metric("Datos propios", orig.get("own_data_markers", 0))
        st.caption(help_text.get("own_data_markers", ""))
    with cols[3]:
        st.metric("Nivel exigido", orig.get("level", "—"))
        st.caption(help_text.get("level", ""))


def render_findings_table(report) -> None:
    import pandas as pd

    from savt.report_builder import findings_dataframe_rows
    from savt.taxonomy import AUDIT_AREAS, SEVERITY_LABELS

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
        st.dataframe(filtered, hide_index=True)


def render_final_report(report, dashboard: dict, base_name: str) -> None:
    import pandas as pd
    from savt.export_docx import build_report_docx
    from savt.export_xlsx import build_report_xlsx
    from savt.report_builder import findings_dataframe_rows

    st.markdown("## Informe final SAVT")
    st.caption(
        "Descargue el informe completo en Excel o Word, o explore el detalle tabular de hallazgos."
    )
    render_findings_table(report)
    render_bibliography_table(report)

    col_csv, col_xlsx, col_docx = st.columns(3)
    csv = pd.DataFrame(findings_dataframe_rows(report)).to_csv(index=False).encode("utf-8")
    with col_csv:
        st.download_button(
            "Descargar CSV (hallazgos)",
            data=csv,
            file_name=f"informe_savt_{base_name}.csv",
            mime="text/csv",
        )
    with col_xlsx:
        xlsx_bytes = build_report_xlsx(report, dashboard)
        st.download_button(
            "Descargar Excel (.xlsx)",
            data=xlsx_bytes,
            file_name=f"informe_savt_{base_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with col_docx:
        docx_bytes = build_report_docx(report, dashboard)
        st.download_button(
            "Descargar Word (.docx)",
            data=docx_bytes,
            file_name=f"informe_savt_{base_name}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


def render_bibliography_and_citation(dashboard: dict) -> None:
    render_bibliography(dashboard)
    render_figures_tables(dashboard)


def render_critical_findings(dashboard: dict) -> None:
    summary = dashboard.get("critical_findings") or {}
    top = summary.get("top_critical") or []
    bib_count = summary.get("bibliography_issue_count", 0)
    suppressed = summary.get("suppressed_duplicates", 0)

    st.markdown("## Hallazgos críticos")
    st.caption(
        "Top problemas priorizados por gravedad. No repite apartados ni bibliografía ya detallados arriba."
    )

    if bib_count:
        label = "crítico" if bib_count == 1 else "críticos"
        st.info(
            f"Se detectaron **{bib_count}** problema(s) bibliográfico(s) {label}. "
            "Ver detalle en la sección **Bibliografía y citación**."
        )

    if not top and bib_count == 0:
        st.success("No se detectaron problemas críticos adicionales fuera de los apartados señalados.")
        return

    for idx, item in enumerate(top, start=1):
        st.markdown(f"**{idx}. {item['title']}**")
        st.caption(item.get("gravity", ""))
        with st.expander("Ver detalle", expanded=False):
            if item.get("detail"):
                st.write(item["detail"])
            if item.get("how_to_fix"):
                st.caption(f"Cómo corregir: {item['how_to_fix']}")

    if suppressed:
        st.caption(
            f"{suppressed} hallazgo(s) omitido(s) aquí porque ya están explicados en "
            "«Apartados con observaciones»."
        )


def render_hallazgos(dashboard: dict) -> None:
    """Compatibilidad: delega en hallazgos críticos."""
    render_critical_findings(dashboard)


def render_bibliography_table(report) -> None:
    import pandas as pd

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
        st.dataframe(pd.DataFrame(rows), hide_index=True)


def main() -> None:
    try:
        _run_app()
    except Exception as exc:
        st.error("SAVT encontró un error inesperado. Detalle técnico:")
        st.exception(exc)
        st.info(
            "Si el problema persiste, reinicie la app en Streamlit Cloud "
            "(Manage app → Reboot app) o vuelva a ejecutar la auditoría."
        )


def _run_app() -> None:
    global LOGO_PATH, conformance_badge, conformance_label, readiness_conformance_badge
    LOGO_PATH, conformance_badge, conformance_label, readiness_conformance_badge = _lazy_ui()

    if sys.version_info >= (3, 13):
        st.sidebar.warning(
            "Entorno Python "
            f"{sys.version.split()[0]}: si la app falla, redeploy en Streamlit Cloud con Python 3.11."
        )

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
            "El informe cubre estructura, normativa, integridad, ética y profundidad."
        )
        return

    if st.button("Ejecutar auditoría", type="primary"):
        progress_bar = st.progress(0.0)
        status_box = st.empty()
        preview_box = st.empty()

        def on_progress(phase: str, detail: str, fraction: float, payload: dict | None = None) -> None:
            progress_bar.progress(min(max(fraction, 0.0), 1.0))
            status_box.markdown(f"**{phase}** — {detail}")
            if payload and payload.get("detected_sections"):
                preview_box.markdown("#### Apartados detectados hasta el momento")
                preview_rows = [
                    {
                        "Apartado": s.get("title"),
                        "Detectado como": s.get("detected_as"),
                        "Palabras": s.get("words"),
                        "%": s.get("percent_label"),
                    }
                    for s in payload["detected_sections"]
                ]
                preview_box.dataframe(preview_rows, hide_index=True)

        with st.spinner("Analizando tesis…"):
            from savt.audit import run_audit

            report = run_audit(
                io.BytesIO(uploaded.getvalue()),
                filename=uploaded.name,
                config=config,
                on_progress=on_progress,
            )
        progress_bar.progress(1.0)
        status_box.success("Auditoría completada.")
        preview_box.empty()
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

    base_name = uploaded.name.rsplit(".", 1)[0]

    render_document_data(dashboard, report)
    st.divider()
    render_verdict(dashboard)
    st.divider()
    render_checklist(dashboard)
    st.divider()
    render_apartados_con_observaciones(dashboard)
    st.divider()
    render_bibliography_and_citation(dashboard)
    st.divider()
    render_integrity(dashboard)
    st.divider()
    render_ethics(dashboard)
    st.divider()
    render_academic_depth(dashboard)
    st.divider()
    render_originality(dashboard)
    st.divider()
    render_critical_findings(dashboard)
    st.divider()
    render_jury(dashboard)
    st.divider()
    render_technical_section_detail(dashboard)
    st.divider()
    render_final_report(report, dashboard, base_name)


if __name__ == "__main__":
    main()
