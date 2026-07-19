"""Interfaz Streamlit completa de SAVT."""

from __future__ import annotations

import io
import sys

import streamlit as st


def _lazy_ui():
    from savt.ui_branding import LOGO_PATH, inject_branding
    from savt.ui_labels import (
        conformance_badge,
        conformance_label,
        readiness_conformance_badge,
    )

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
            if report.page_estimate < min_pages or report.page_estimate > max_pages:
                st.warning(f"Extensión fuera del rango {min_pages}–{max_pages} páginas.")

    st.sidebar.markdown("---")
    usage_count = st.session_state.get("usage_count")
    if usage_count is None:
        try:
            from savt.usage_counter import get_usage_count

            usage_count = get_usage_count()
        except Exception:
            usage_count = None
    if usage_count is not None:
        st.sidebar.caption(f"Auditorías realizadas: {usage_count:,}")
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


def _review_status_label(review: dict) -> str:
    if review.get("ok"):
        return "Completo"
    if review.get("partial"):
        return "Revisión parcial recomendada"
    return "Requiere revisión"


def _words_by_canonical_role(dashboard: dict) -> dict[str, int]:
    """Palabras por rol canónico (preferir canonical_words del dashboard)."""
    direct = dashboard.get("canonical_words") or {}
    if direct:
        return {str(k): int(v or 0) for k, v in direct.items()}
    words: dict[str, int] = {}
    for item in (dashboard.get("content_dashboard") or {}).get("section_depth") or []:
        role = item.get("role") or item.get("section_key") or item.get("key")
        if role:
            words[str(role)] = int(item.get("words") or 0)
    return words


def render_document_chapters(dashboard: dict) -> None:
    """1) Capítulos / bloques estructurales con palabras y %."""
    detected = dashboard.get("detected_sections") or []
    model = dashboard.get("document_model") or {}
    chapters = model.get("chapters") or []
    thesis_type = dashboard.get("thesis_type") or "clasica"

    st.markdown("## 1. Capítulos y estructura del documento")
    if thesis_type == "compendio":
        st.caption(
            "Tesis por **capítulos / compendio**. Esto es lo primero que debe ver: "
            "qué contiene el documento, cuántas palabras y qué porcentaje representa."
        )
    else:
        st.caption("Bloques principales detectados en el documento (palabras y peso relativo).")

    rows = []
    if chapters:
        total = max(sum(int(c.get("words") or 0) for c in chapters), 1)
        for idx, chapter in enumerate(chapters, start=1):
            words = int(chapter.get("words") or 0)
            pct = round(words * 100 / total, 1)
            rows.append(
                {
                    "N°": idx,
                    "Capítulo / apartado": chapter.get("title") or "—",
                    "Palabras": words,
                    "% del documento": f"{pct:.1f}%",
                }
            )
    else:
        for idx, item in enumerate(detected, start=1):
            rows.append(
                {
                    "N°": item.get("order", idx),
                    "Capítulo / apartado": item.get("path") or item.get("detected_as") or item.get("title") or "—",
                    "Palabras": item.get("words", 0),
                    "% del documento": item.get("percent_label", "—"),
                }
            )

    if not rows:
        st.warning("No se identificaron capítulos o apartados estructurales.")
        return

    st.dataframe(rows, hide_index=True, use_container_width=True)
    total_words = sum(int(r["Palabras"]) for r in rows)
    st.caption(f"**{len(rows)}** bloques · **{total_words:,}** palabras clasificadas.")

    tree = dashboard.get("structure_tree") or []
    if tree:
        with st.expander("Ver subtítulos dentro de cada capítulo", expanded=False):
            for node in tree:
                st.markdown(f"**{node.get('title')}** — {int(node.get('words') or 0):,} palabras")
                for child in node.get("children") or []:
                    st.markdown(f"- {child.get('title')} ({int(child.get('words') or 0):,} palabras)")


def render_evaluation_checklist(dashboard: dict) -> None:
    """2) Checklist compacto (una sola vez)."""
    checklist = dashboard.get("checklist") or {}
    items = checklist.get("items") or []
    reviews = {r.get("key"): r for r in (dashboard.get("chapter_reviews") or [])}

    st.markdown("## 2. Checklist de evaluación")
    st.caption(
        "Estado de los apartados académicos: Introducción, Objetivos, Marco teórico, "
        "Metodología, Resultados, Discusión, Conclusiones, Bibliografía."
    )
    st.markdown(f"**Estado general:** {checklist.get('status', '—')}")

    if not items:
        st.info("No hay checklist disponible.")
        return

    rows = []
    for item in items:
        key = item.get("section_key") or ""
        review = reviews.get(key) or {}
        title = review.get("title") or (item.get("label") or "—").split(" — ")[0].replace(" completo", "")
        if item.get("ok"):
            estado = "Completo"
        elif item.get("partial"):
            estado = "Revisión parcial"
        else:
            estado = "Requiere revisión"
        rows.append({"Apartado": title, "Estado": estado})

    st.dataframe(rows, hide_index=True, use_container_width=True)


def render_canonical_apartados(dashboard: dict) -> None:
    """3) Tabla canónica + detalle solo de lo que hay que corregir."""
    reviews = dashboard.get("chapter_reviews") or []

    st.markdown("## 3. Apartados de evaluación")
    st.caption(
        "Los mismos apartados del checklist, con estado y un resumen corto. "
        "El detalle de corrección aparece solo donde hace falta revisar."
    )

    if not reviews:
        st.warning("No hay revisión por apartado.")
        return

    rows = []
    pending = []
    for review in reviews:
        rows.append(
            {
                "Apartado": review.get("title") or review.get("key") or "—",
                "Estado": _review_status_label(review),
                "Resumen": (review.get("summary") or "")[:220],
            }
        )
        if not review.get("ok"):
            pending.append(review)

    st.dataframe(rows, hide_index=True, use_container_width=True)

    if not pending:
        st.success("Todos los apartados evaluados están completos según la detección automática.")
        return

    st.markdown("### Qué revisar y cómo corregir")
    for review in pending:
        status = _review_status_label(review)
        with st.expander(f"{review.get('title')} — {status}", expanded=True):
            if review.get("summary"):
                st.write(review["summary"])
            if review.get("why"):
                st.markdown(f"**Por qué importa:** {review['why']}")
            if review.get("how_to_fix"):
                st.info(f"**Cómo corregir:** {review['how_to_fix']}")


def render_priority_findings(dashboard: dict) -> None:
    """Hallazgos prioritarios (una sola vez; no repetir checklist)."""
    warnings = dashboard.get("warnings_list") or []
    st.markdown("## 4. Hallazgos prioritarios")
    st.caption("Alertas concretas a corregir antes de presentar (no repite el checklist).")
    if not warnings:
        st.success("No hay advertencias prioritarias listadas.")
        return
    for idx, item in enumerate(warnings[:10], start=1):
        st.markdown(f"**{idx}. {item.get('title', 'Hallazgo')}**")
        st.caption(item.get("gravity") or "")
        detail = item.get("detail")
        if detail:
            st.write(str(detail)[:350])


def render_extra_evidence(dashboard: dict) -> None:
    """Detalle adicional único: citas, profundidad, bibliografía numérica."""
    st.markdown("## 5. Evidencia adicional")
    st.caption("Información que no está arriba: citas, profundidad y datos de bibliografía.")

    with st.expander("Cuadre de citas y referencias", expanded=False):
        recon = dashboard.get("citation_reconciliation") or {}
        rows = recon.get("reconciliation_rows") or []
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        for note in recon.get("notes") or []:
            st.caption(note)
        if not rows and not recon.get("notes"):
            st.caption("Sin cuadre de citas disponible.")

    with st.expander("Profundidad académica", expanded=False):
        depth = (dashboard.get("content_dashboard") or {}).get("section_depth") or []
        rows = [
            {
                "Apartado": d.get("title") or d.get("detected_as") or d.get("role") or "—",
                "Palabras": d.get("words", 0),
                "Profundidad": d.get("depth_status_label") or d.get("depth_status") or "—",
                "Motivo": (d.get("reason") or d.get("motivo") or "")[:160],
            }
            for d in depth
            if int(d.get("words") or 0) > 0 or d.get("depth_status") not in {None, "missing"}
        ]
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.caption("Sin datos de profundidad.")

    with st.expander("Bibliografía (cifras)", expanded=False):
        bib = dashboard.get("bibliography_dashboard") or {}
        details = bib.get("details") or {}
        total = bib.get("total") or details.get("total") or bib.get("entry_count") or "—"
        st.write(
            f"Estilo: **{bib.get('style') or details.get('style') or 'APA'}** · "
            f"Entradas detectadas: **{total}**"
        )
        for review in dashboard.get("chapter_reviews") or []:
            if review.get("key") == "bibliografia":
                for issue in review.get("issues") or []:
                    st.markdown(f"- {issue}")


def render_executive_report(dashboard: dict, report, base_name: str) -> None:
    """
    Pantalla principal sin redundancia:
    resultado → capítulos → checklist → apartados → hallazgos → evidencia → descargas.
    """
    st.markdown("## Resultado de la auditoría")
    left, right = st.columns([1, 1.2])
    with left:
        st.markdown(f"### ICAI **{dashboard.get('icai', '—')}/100**")
        st.caption(dashboard.get("icai_interpretation") or "")
        try:
            st.progress(min(int(dashboard.get("icai") or 0), 100) / 100)
        except Exception:
            pass
    with right:
        st.markdown(
            f"### {readiness_conformance_badge(dashboard.get('readiness') or '')}",
            unsafe_allow_html=True,
        )
        st.markdown(f"**{dashboard.get('readiness') or '—'}**")
        st.markdown(f"**Motivo principal:** {dashboard.get('main_reason') or '—'}")
        if dashboard.get("profile_label"):
            st.caption(f"Perfil: {dashboard.get('profile_label')}")

    st.divider()
    render_document_chapters(dashboard)
    st.divider()
    render_evaluation_checklist(dashboard)
    st.divider()
    render_canonical_apartados(dashboard)
    st.divider()
    render_priority_findings(dashboard)
    st.divider()
    render_extra_evidence(dashboard)
    st.divider()

    with st.expander("Integridad, ética, originalidad y jurado", expanded=False):
        render_integrity(dashboard)
        render_ethics(dashboard)
        render_originality(dashboard)
        render_jury(dashboard)

    st.divider()
    render_final_report(report, dashboard, base_name)


def render_detected_sections(dashboard: dict) -> None:
    """Compatibilidad: redirige a la vista de capítulos."""
    render_document_chapters(dashboard)


def render_structure_confirmation(sections: list[dict], structure_source: str = "") -> dict | None:
    """
    Pantalla de estructura: automática (editable) o manual (índice pegado por el usuario).
    Devuelve:
      {"mode": "overrides", "overrides": [...]}
      {"mode": "manual", "entries": [...]}
      None si aún no confirma.
    """
    from savt.structure_confirm import (
        CANONICAL_TEMPLATE_OUTLINE,
        MANUAL_OUTLINE_PLACEHOLDER,
        editor_rows,
        overrides_from_editor,
        parse_manual_outline,
        role_options,
        structure_confidence_summary,
        ROLE_LABELS,
    )

    st.markdown("## 1. Estructura del documento")
    st.caption(
        "Si la detección automática mezcla capítulos y subtítulos, use la pestaña "
        "**Ingresar índice manualmente** y pegue la tabla de contenido real."
    )

    tab_auto, tab_manual = st.tabs(["Automática (detectada)", "Ingresar índice manualmente"])

    with tab_auto:
        if structure_source:
            source_label = {
                "index": "índice del documento",
                "capitulos": "capítulos del cuerpo (tesis por compendio)",
                "headings": "encabezados del cuerpo",
                "confirmed": "confirmación previa",
                "manual": "estructura manual",
            }.get(structure_source, structure_source)
            st.caption(f"Fuente de detección: **{source_label}**.")
            if structure_source == "capitulos":
                st.info(
                    "Se detectó una **tesis por capítulos**. "
                    "La tabla muestra capítulos (nivel 1), no subtítulos sueltos."
                )

        summary = structure_confidence_summary(sections)
        if not sections:
            st.warning("No se identificaron apartados automáticamente. Use la pestaña manual.")
        elif summary["needs_review"]:
            st.warning(
                f"Hay {summary['low']} apartado(s) con confianza baja y {summary['medium']} con confianza media. "
                "Si el mapa no coincide con su tesis, pase a la pestaña manual."
            )
        else:
            st.info("Estructura detectada. Puede confirmarla o reemplazarla con su índice real.")

        import pandas as pd

        if sections:
            base_rows = editor_rows(sections)
            st.session_state["_structure_editor_meta"] = [
                {"_role_original": r["_role_original"], "_text_key": r["_text_key"]} for r in base_rows
            ]
            df = pd.DataFrame(
                [
                    {
                        "Incluir": r["Incluir"],
                        "Detectado como": r["Detectado como"],
                        "Apartado canónico": r["Apartado canónico"],
                        "Confianza": r["Confianza"],
                        "Palabras": r["Palabras"],
                        "% del cuerpo": r["% del cuerpo"],
                    }
                    for r in base_rows
                ]
            )
            edited = st.data_editor(
                df,
                hide_index=True,
                disabled=["Detectado como", "Confianza", "Palabras", "% del cuerpo"],
                column_config={
                    "Incluir": st.column_config.CheckboxColumn("Incluir", default=True),
                    "Apartado canónico": st.column_config.SelectboxColumn(
                        "Apartado canónico",
                        options=role_options(),
                        required=True,
                    ),
                },
                use_container_width=True,
                key="structure_editor_auto",
            )
        else:
            edited = None

        col_a, col_b = st.columns(2)
        with col_a:
            confirm_auto = st.button("Confirmar detección y auditar", type="primary", key="btn_auto_confirm")
        with col_b:
            skip_auto = st.button("Auditar sin cambios", key="btn_auto_skip")

        if confirm_auto or skip_auto:
            if not sections:
                return {"mode": "overrides", "overrides": []}
            if skip_auto:
                return {
                    "mode": "overrides",
                    "overrides": [
                        {
                            "role_original": s.get("role"),
                            "confirmed_role": s.get("role"),
                            "include": True,
                            "detected_as": s.get("detected_as"),
                            "words": s.get("words", 0),
                        }
                        for s in sections
                    ],
                }
            records = edited.to_dict("records") if edited is not None else []
            meta = st.session_state.get("_structure_editor_meta") or []
            for idx, record in enumerate(records):
                if idx < len(meta):
                    record["_role_original"] = meta[idx]["_role_original"]
                    record["_text_key"] = meta[idx]["_text_key"]
            return {"mode": "overrides", "overrides": overrides_from_editor(records)}

    with tab_manual:
        st.markdown("### Pegue su tabla de contenido")
        st.caption(
            "Un título por línea. Si pega desde el PDF, use **Limpiar pegado de PDF** "
            "(une líneas partidas y quita números de página). Mejor aún: deje solo "
            "capítulos y apartados principales. Opcional: rol con `|` "
            "(metodologia, resultados, discusion, …)."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Cargar plantilla canónica", key="btn_tpl_canonical"):
                st.session_state["manual_outline_area"] = CANONICAL_TEMPLATE_OUTLINE
                st.session_state["manual_outline_text"] = CANONICAL_TEMPLATE_OUTLINE
                st.rerun()
        with c2:
            if st.button("Limpiar pegado de PDF", key="btn_tpl_clean_pdf"):
                from savt.structure_confirm import clean_pasted_toc

                raw = st.session_state.get("manual_outline_area") or st.session_state.get(
                    "manual_outline_text", ""
                )
                cleaned = clean_pasted_toc(raw, major_only=True)
                st.session_state["manual_outline_area"] = cleaned
                st.session_state["manual_outline_text"] = cleaned
                st.rerun()
        with c3:
            if st.button("Vaciar", key="btn_tpl_clear"):
                st.session_state["manual_outline_area"] = ""
                st.session_state["manual_outline_text"] = ""
                st.rerun()

        # Solo key (sin value=): evita desfase Streamlit que deja el botón “prohibido”
        # mientras el texto ya se ve en pantalla.
        if "manual_outline_area" not in st.session_state:
            st.session_state["manual_outline_area"] = st.session_state.get("manual_outline_text", "")

        outline_text = st.text_area(
            "Índice / capítulos",
            height=280,
            placeholder=MANUAL_OUTLINE_PLACEHOLDER,
            key="manual_outline_area",
        )
        st.session_state["manual_outline_text"] = outline_text or ""

        parsed_entries = parse_manual_outline(outline_text or "")
        edited_manual = None
        if parsed_entries:
            import pandas as pd

            preview = pd.DataFrame(
                [
                    {
                        "Incluir": e.get("include", True),
                        "Título en el documento": e.get("title", ""),
                        "Apartado canónico": ROLE_LABELS.get(e.get("role", "otros"), ROLE_LABELS["otros"]),
                    }
                    for e in parsed_entries
                ]
            )
            edited_manual = st.data_editor(
                preview,
                hide_index=True,
                column_config={
                    "Incluir": st.column_config.CheckboxColumn("Incluir", default=True),
                    "Título en el documento": st.column_config.TextColumn("Título en el documento", width="large"),
                    "Apartado canónico": st.column_config.SelectboxColumn(
                        "Apartado canónico",
                        options=role_options(),
                        required=True,
                    ),
                },
                num_rows="dynamic",
                use_container_width=True,
                key="manual_outline_editor",
            )
            n_entries = len(edited_manual)
            st.caption(
                f"{n_entries} entradas listas. SAVT buscará cada título en el PDF y cortará los bloques."
            )
            if n_entries > 25:
                st.warning(
                    "Hay muchas entradas (típico al pegar el índice completo del PDF). "
                    "Pulse **Limpiar pegado de PDF** o deje solo 8–15 apartados principales "
                    "para un mejor resultado."
                )
        elif (outline_text or "").strip():
            st.warning(
                "El texto pegado no se pudo interpretar como títulos. "
                "Pruebe **Limpiar pegado de PDF** o deje un título por línea "
                "(ej. CAPÍTULO I, MÉTODOS, RESULTADOS)."
            )
        else:
            st.info(
                "Pegue al menos 2 títulos principales "
                "(por ejemplo CAPÍTULO I, MÉTODOS, RESULTADOS, DISCUSIÓN, REFERENCIAS)."
            )

        # Siempre habilitado: validamos al hacer clic (el cursor 🚫 confundía al usuario).
        confirm_manual = st.button(
            "Localizar títulos y auditar con mi estructura",
            type="primary",
            key="btn_manual_confirm",
        )
        if confirm_manual:
            from savt.structure_confirm import label_to_role

            raw_now = (
                st.session_state.get("manual_outline_area")
                or st.session_state.get("manual_outline_text")
                or outline_text
                or ""
            )
            entries = []
            source_rows = None
            if edited_manual is not None:
                source_rows = edited_manual.to_dict("records")
            else:
                fallback = parse_manual_outline(raw_now)
                source_rows = [
                    {
                        "Incluir": e.get("include", True),
                        "Título en el documento": e.get("title", ""),
                        "Apartado canónico": ROLE_LABELS.get(e.get("role", "otros"), ROLE_LABELS["otros"]),
                    }
                    for e in fallback
                ]

            for row in source_rows or []:
                title = str(row.get("Título en el documento") or "").strip()
                if not title:
                    continue
                role = label_to_role(str(row.get("Apartado canónico") or ROLE_LABELS["otros"]))
                entries.append(
                    {
                        "title": title,
                        "role": role,
                        "include": bool(row.get("Incluir", True)),
                    }
                )
            if len(entries) < 2:
                st.error(
                    "Ingrese al menos dos títulos válidos (uno por línea) y vuelva a pulsar el botón."
                )
            else:
                return {"mode": "manual", "entries": entries}

    return None


def render_technical_section_detail(dashboard: dict) -> None:
    """Métricas por apartado y cuadre de citas — colapsado para no duplicar el informe principal."""
    from savt.section_audit import section_audit_summary_rows

    section_audits = dashboard.get("section_audits") or []
    if not section_audits:
        return

    with st.expander("Detalle técnico: métricas por apartado", expanded=False):
        st.caption(
            "Vista analítica para revisión avanzada (sin recuentos numéricos)."
        )
        if section_audits:
            rows = section_audit_summary_rows(section_audits)
            display = [
                {
                    "Apartado": row.get("Apartado", ""),
                    "Detectado como": row.get("Detectado como", ""),
                    "Estado": row.get("Estado", "—"),
                    "Profundidad": row.get("Profundidad", "—"),
                    "Observaciones": row.get("Observaciones", ""),
                }
                for row in rows
            ]
            st.dataframe(display, hide_index=True)


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

    coverage_ok = bib["coverage"] == "adecuada"
    coverage_partial = bib["coverage"] not in ("adecuada", "—")

    summary_lines = [
        f"{conformance_badge(bib.get('style_ok', True))} — Estilo {bib['style']} detectado",
    ]
    if bib["out_of_period"]:
        summary_lines.append(
            f"{conformance_badge(False, True)} — Referencias fuera del período metodológico"
        )
    if bib["possibly_off_topic"]:
        summary_lines.append(
            f"{conformance_badge(False, True)} — Referencias posiblemente ajenas al tema"
        )
    summary_lines.append(
        f"{conformance_badge(coverage_ok, coverage_partial)} — "
        f"Cobertura bibliográfica {bib['coverage']}"
    )
    for line in summary_lines:
        st.markdown(line, unsafe_allow_html=True)

    unmatched = details.get("unmatched_apa") or []
    if unmatched:
        with st.expander("Citas no emparejadas", expanded=True):
            for entry in unmatched:
                cites = ", ".join(entry["citations_in_text"])
                st.markdown(f"- **En el texto:** {cites}")
                st.caption(f"Clave detectada: `{entry['key']}` — {entry['hint']}")

    out_of_period = details.get("out_of_period") or []
    if out_of_period:
        period = out_of_period[0].get("period_declared", "")
        with st.expander(f"Referencias anteriores al período {period}", expanded=False):
            for entry in out_of_period[:20]:
                st.markdown(f"- **Ref. {entry['number']} ({entry['year']}):** {entry['summary']}")

    off_topic = details.get("off_topic") or []
    if off_topic:
        with st.expander("Referencias posiblemente ajenas al tema", expanded=False):
            for entry in off_topic[:20]:
                st.markdown(f"- **Ref. {entry['number']}:** {entry['summary']}")
                st.caption(entry.get("reason", ""))

    doi_invalid = details.get("doi_invalid") or []
    doi_not_resolved = details.get("doi_not_resolved") or []
    doi_network = details.get("doi_network") or []
    doi_year = details.get("doi_year_mismatch") or []
    doi_help = details.get("doi_help") or {}

    if doi_invalid or doi_not_resolved:
        with st.expander("DOI inválidos / no resueltos", expanded=True):
            st.markdown(doi_help.get("invalid", ""))
            for entry in doi_invalid:
                st.markdown(f"- **Ref. {entry['number']}:** [{entry['doi_url']}]({entry['doi_url']})")
                st.caption(entry["message"])
            st.markdown(doi_help.get("not_resolved", ""))
            for entry in doi_not_resolved:
                st.markdown(f"- **Ref. {entry['number']}:** [{entry['doi_url']}]({entry['doi_url']})")
                st.caption(f"{entry['message']} — {entry['summary'][:100]}…")

    if doi_year:
        with st.expander("Año distinto al registrado en Crossref", expanded=False):
            st.markdown(doi_help.get("year_mismatch", ""))
            for entry in doi_year:
                st.markdown(
                    f"- **Ref. {entry['number']}:** bibliografía **{entry['year_in_bibliography']}** "
                    f"vs Crossref **{entry['year_in_crossref']}**"
                )
                st.markdown(f"  [{entry['doi_url']}]({entry['doi_url']})")
                st.caption(entry["summary"])

    if doi_network:
        with st.expander("DOI no verificados por red", expanded=False):
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
        preview = formal.get("abstract_text_preview", "")
        if preview:
            st.markdown("**Resumen:**")
            st.caption(preview + "…")


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


def render_pipeline_steps(pipeline: list[dict], structure_source: str | None = None) -> None:
    """Muestra el flujo en cuatro momentos: índice → apartados → bibliografía → referencias."""
    if not pipeline:
        return
    st.markdown("### Procesamiento del documento")
    source_hint = "índice" if structure_source == "index" else "encabezados del texto"
    st.caption(
        f"Flujo en cuatro pasos. Apartados tomados del {source_hint}; "
        "referencias solo del apartado bibliográfico (sin escanear el cuerpo)."
    )
    icons = {"ok": "✅", "warning": "⚠️", "error": "❌", "skipped": "⏭️"}
    for step in pipeline:
        icon = icons.get(step.get("status", ""), "•")
        st.markdown(f"**{icon} {step.get('title', '—')}** — {step.get('summary', '')}")


def render_document_data(dashboard: dict, report) -> None:
    formal = dashboard.get("formal_dashboard") or {}
    st.markdown("## Datos del documento")
    st.caption(f"Perfil: {dashboard.get('profile_label', '—')}")

    render_pipeline_steps(
        dashboard.get("pipeline") or report.metadata.get("pipeline") or [],
        dashboard.get("structure_source") or report.metadata.get("structure_source"),
    )

    if formal:
        with st.expander("Normativa formal detectada", expanded=False):
            render_formal(dashboard)


def render_originality(dashboard: dict) -> None:
    orig = dashboard.get("originality_dashboard") or {}
    if not orig:
        return
    st.markdown("## Originalidad y aporte")
    st.caption(
        "Indicadores heurísticos — no sustituyen evaluación de originalidad por el jurado."
    )
    level_label = orig.get("level_label") or orig.get("level", "—")
    if level_label and level_label != "—":
        st.markdown(f"**Nivel exigido:** {level_label}")
    summary = orig.get("qualitative_summary", "").strip()
    if summary:
        st.markdown("**Análisis cualitativo**")
        st.write(summary)


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

    st.markdown("## Descargar informe")
    st.caption(
        "Excel, Word o JSON para archivo. La pantalla de arriba ya muestra lo esencial; "
        "no hace falta abrir el Excel para entender el resultado."
    )
    render_findings_table(report)

    col_csv, col_xlsx, col_docx, col_json = st.columns(4)
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
    with col_json:
        from savt.document_model import document_model_to_json

        model = dashboard.get("document_model") or {}
        st.download_button(
            "Descargar JSON (estructura)",
            data=document_model_to_json(model).encode("utf-8"),
            file_name=f"documento_estructurado_{base_name}.json",
            mime="application/json",
            help="Representación semántica del documento (capítulos/secciones). Base del motor documental.",
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
        st.info(
            "Hay problemas bibliográficos pendientes. "
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
            "Algunos hallazgos omitidos aquí porque ya están explicados en "
            "«Apartados con observaciones»."
        )


def render_hallazgos(dashboard: dict) -> None:
    """Compatibilidad: delega en hallazgos críticos."""
    render_critical_findings(dashboard)


def render_user_feedback(*, context: dict | None = None) -> None:
    from savt import __version__
    from savt.user_feedback import submit_user_feedback

    ctx = context or {}
    st.markdown("## Valoración del sistema")
    st.caption(
        "¿Qué le pareció SAVT? Su calificación y comentarios nos ayudan a mejorar la herramienta."
    )

    with st.form("savt_user_feedback", clear_on_submit=True):
        rating = st.select_slider(
            "Calificación general",
            options=[1, 2, 3, 4, 5],
            value=4,
            format_func=lambda value: "★" * value + "☆" * (5 - value),
            help="1 = muy insatisfecho · 5 = muy satisfecho",
        )
        comment = st.text_area(
            "Su opinión (opcional)",
            height=120,
            placeholder=(
                "Ej.: qué le resultó útil, qué faltaría, si el informe fue claro, "
                "sugerencias para directores o estudiantes…"
            ),
        )
        submitted = st.form_submit_button("Enviar valoración", type="secondary")

    if not submitted:
        return

    ok, message = submit_user_feedback(
        rating,
        comment,
        version=__version__,
        filename=str(ctx.get("filename", "")),
        icai=ctx.get("icai"),
        profile=str(ctx.get("profile", "")),
    )
    if ok:
        st.success(message)
    else:
        st.error(message)


def run_app() -> None:
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
        for key in ("parsed_doc", "detected_sections", "structure_ready", "report", "manual_outline_text"):
            st.session_state.pop(key, None)
        st.info(
            "Suba un archivo .docx o .pdf para iniciar la pre-auditoría académica. "
            "Podrá confirmar la estructura detectada o **pegar su índice manualmente**. "
            "Seleccione el perfil institucional en la barra lateral."
        )
        st.divider()
        render_user_feedback()
        return

    # Nuevo archivo: limpiar estado de estructura/informe previos.
    if st.session_state.get("uploaded_name") != uploaded.name:
        st.session_state["uploaded_name"] = uploaded.name
        for key in ("parsed_doc", "detected_sections", "structure_ready", "report", "manual_outline_text"):
            st.session_state.pop(key, None)

    parsed = st.session_state.get("parsed_doc")
    detected = st.session_state.get("detected_sections")
    has_report = bool(st.session_state.get("report"))

    # Si hay informe, no exigir de nuevo la detección (evita volver al paso 1 tras auditar).
    if (parsed is None or detected is None) and not has_report:
        if st.button("1. Detectar estructura", type="primary"):
            with st.spinner("Extrayendo texto y localizando apartados…"):
                from savt.audit import prepare_document

                parsed, resolved_config, detected = prepare_document(
                    io.BytesIO(uploaded.getvalue()),
                    filename=uploaded.name,
                    config=config,
                )
            st.session_state["parsed_doc"] = parsed
            st.session_state["detected_sections"] = detected
            st.session_state["resolved_config"] = resolved_config
            st.session_state.pop("report", None)
            st.rerun()
        st.info(
            "Paso 1: detectar la estructura automática. "
            "Si no coincide con su tesis, use la pestaña **Ingresar índice manualmente**."
        )
        st.divider()
        render_user_feedback(context={"filename": uploaded.name})
        return

    structure_choice = None
    if not st.session_state.get("report"):
        structure_choice = render_structure_confirmation(
            detected or [],
            structure_source=str((parsed or {}).get("structure_source") or ""),
        )
        if structure_choice is None:
            st.divider()
            render_user_feedback(context={"filename": uploaded.name})
            return

        from savt.document_model import build_document_model
        from savt.section_audit import detect_document_sections
        from savt.structure_confirm import apply_manual_outline, apply_section_overrides

        if structure_choice.get("mode") == "manual":
            parsed = apply_manual_outline(parsed, structure_choice.get("entries") or [])
            missing = parsed.get("manual_missing_titles") or []
            if missing:
                st.warning(
                    "No se localizaron en el PDF estos títulos (revise ortografía o acorte el texto): "
                    + "; ".join(missing[:8])
                    + ("…" if len(missing) > 8 else "")
                )
            found = len(parsed.get("index_sections") or [])
            if found < 2:
                st.error(
                    "Con la estructura manual solo se localizaron menos de 2 apartados en el texto. "
                    "Use **Limpiar pegado de PDF**, deje solo capítulos/apartados principales "
                    "(CAPÍTULO I, MÉTODOS, RESULTADOS…) y reintente."
                )
                st.divider()
                render_user_feedback(context={"filename": uploaded.name})
                return
            # Mantener detected_sections actualizado (no None): si queda None, un rerun
            # vuelve incorrectamente a «1. Detectar estructura».
            parsed["document_model"] = build_document_model(parsed)
            st.session_state["detected_sections"] = detect_document_sections(parsed)
        else:
            parsed = apply_section_overrides(parsed, structure_choice.get("overrides") or [])
            parsed["document_model"] = build_document_model(parsed)
            st.session_state["detected_sections"] = detect_document_sections(parsed)
        st.session_state["parsed_doc"] = parsed

        progress_bar = st.progress(0.0)
        status_box = st.empty()

        def on_progress(phase: str, detail: str, fraction: float, payload: dict | None = None) -> None:
            progress_bar.progress(min(max(fraction, 0.0), 1.0))
            status_box.markdown(f"**{phase}** — {detail}")

        try:
            with st.spinner("Auditando tesis con la estructura confirmada…"):
                from savt.audit import run_audit_from_parsed

                resolved = st.session_state.get("resolved_config") or config
                report = run_audit_from_parsed(
                    parsed,
                    filename=uploaded.name,
                    config=resolved,
                    on_progress=on_progress,
                )
        except Exception as exc:
            st.error("La auditoría falló tras confirmar la estructura. Puede reintentar sin perder el PDF.")
            st.exception(exc)
            st.divider()
            render_user_feedback(context={"filename": uploaded.name})
            return

        progress_bar.progress(1.0)
        status_box.success("Auditoría completada.")
        try:
            from savt.usage_counter import record_audit_usage

            usage_count = record_audit_usage()
            if usage_count is not None:
                st.session_state["usage_count"] = usage_count
        except Exception:
            pass
        st.session_state["report"] = report
        st.session_state["profile_id"] = resolved.profile_id
        st.rerun()

    report = st.session_state.get("report")
    if not report or report.filename != uploaded.name:
        st.divider()
        render_user_feedback(context={"filename": uploaded.name})
        return

    dashboard = report.metadata.get("dashboard", {})
    if not dashboard:
        st.error("Informe incompleto. Vuelva a ejecutar la auditoría.")
        st.divider()
        render_user_feedback(context={"filename": uploaded.name})
        return

    if st.button("↩ Revisar estructura y reauditar"):
        st.session_state.pop("report", None)
        st.rerun()

    base_name = uploaded.name.rsplit(".", 1)[0]
    render_executive_report(dashboard, report, base_name)
    st.divider()
    render_user_feedback(
        context={
            "filename": uploaded.name,
            "icai": dashboard.get("icai"),
            "profile": dashboard.get("profile_label", ""),
        }
    )
