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
                    Pre-auditoría académica por apartados: pegue introducción, marco, metodología,
                    resultados, discusión, conclusiones y bibliografía.
                    Genera observaciones y recomendaciones antes de la evaluación del jurado.
                </p>
                <p class="savt-institution">Universidad Católica de Cuyo · Observatorio de Inteligencia Artificial</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _clear_audit_session_keys() -> None:
    for key in (
        "parsed_doc",
        "detected_sections",
        "structure_ready",
        "report",
        "manual_outline_text",
        "index_reviewed_checkbox",
        "index_confirmation_editor",
        "uploaded_name",
        "paste_doc_name",
        "resolved_config",
    ):
        st.session_state.pop(key, None)


def render_paste_sections_form() -> list[dict] | None:
    """Formulario de carga por apartados. Devuelve entradas listas para auditar o None."""
    from savt.paste_sections import (
        EXTRA_ROLE_OPTIONS,
        paste_entries_summary,
        paste_field_specs,
    )

    st.markdown("### Carga por apartados")
    st.caption(
        "Pegue el texto de cada sección desde su tesis. "
        "Deje vacío lo que no aplique. Puede agregar apartados extras al final."
    )

    doc_title = st.text_input(
        "Título del trabajo (opcional)",
        key="paste_document_title",
        placeholder="Ej.: Producción de PHA con Cupriavidus necator",
    )

    specs = paste_field_specs()
    collected: list[dict] = []

    for spec in specs:
        label = spec["label"]
        if spec.get("required_hint"):
            label = f"{label} *"
        text = st.text_area(
            label,
            key=f"paste_field_{spec['id']}",
            height=int(spec.get("height") or 140),
            help=spec.get("help") or "",
            placeholder=f"Pegue aquí el apartado «{spec['label']}»…",
        )
        if (text or "").strip():
            collected.append(
                {
                    "id": spec["id"],
                    "role": spec["role"],
                    "title": spec["label"],
                    "text": text,
                }
            )

    st.markdown("#### Apartados adicionales")
    st.caption("Si su tesis tiene secciones con otros nombres, agréguelas aquí.")

    if "paste_extra_count" not in st.session_state:
        st.session_state["paste_extra_count"] = 0

    cols_add = st.columns([1, 3])
    with cols_add[0]:
        if st.button("＋ Agregar apartado", key="btn_paste_add_extra"):
            st.session_state["paste_extra_count"] = int(st.session_state.get("paste_extra_count") or 0) + 1
            st.rerun()
    with cols_add[1]:
        if st.session_state.get("paste_extra_count") and st.button(
            "Quitar último apartado extra", key="btn_paste_remove_extra"
        ):
            st.session_state["paste_extra_count"] = max(
                0, int(st.session_state.get("paste_extra_count") or 0) - 1
            )
            st.rerun()

    role_labels = [label for _, label in EXTRA_ROLE_OPTIONS]
    role_by_label = {label: role for role, label in EXTRA_ROLE_OPTIONS}

    for i in range(int(st.session_state.get("paste_extra_count") or 0)):
        with st.expander(f"Apartado extra {i + 1}", expanded=True):
            title = st.text_input(
                "Nombre del apartado",
                key=f"paste_extra_title_{i}",
                placeholder="Ej.: Anexos, Marco normativo, Limitaciones…",
            )
            role_label = st.selectbox(
                "Rol académico equivalente",
                options=role_labels,
                index=role_labels.index("Otro / sin clasificar")
                if "Otro / sin clasificar" in role_labels
                else 0,
                key=f"paste_extra_role_{i}",
            )
            text = st.text_area(
                "Texto",
                key=f"paste_extra_text_{i}",
                height=140,
                placeholder="Pegue el contenido de este apartado…",
            )
            if (text or "").strip():
                collected.append(
                    {
                        "id": f"extra_{i}_{_safe_slug(title or f'extra-{i}')}",
                        "role": role_by_label.get(role_label, "otros"),
                        "title": (title or "").strip() or f"Apartado extra {i + 1}",
                        "text": text,
                    }
                )

    st.info(paste_entries_summary(collected))
    st.caption("* Campos recomendados para una auditoría completa (pueden quedar vacíos si no aplican).")

    if st.button("Auditar apartados pegados", type="primary", key="btn_paste_audit"):
        return collected
    return None


def _safe_slug(text: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:32] or "extra"


def _run_paste_mode(config) -> None:
    """Flujo completo: pegar apartados → auditar → informe."""
    report = st.session_state.get("report")
    paste_name = st.session_state.get("paste_doc_name") or "tesis-por-apartados.txt"

    if report and getattr(report, "filename", None) == paste_name:
        if st.button("↩ Editar apartados y reauditar", key="btn_paste_reedit"):
            st.session_state.pop("report", None)
            st.session_state.pop("parsed_doc", None)
            st.rerun()

        dashboard = report.metadata.get("dashboard", {})
        if not dashboard:
            st.error("Informe incompleto. Vuelva a ejecutar la auditoría.")
            st.divider()
            render_user_feedback(context={"filename": paste_name, "mode": "paste"})
            return

        base_name = paste_name.rsplit(".", 1)[0]
        render_executive_report(dashboard, report, base_name)
        st.divider()
        render_user_feedback(
            context={
                "filename": paste_name,
                "mode": "paste",
                "icai": dashboard.get("icai"),
                "profile": dashboard.get("profile_label", ""),
            }
        )
        return

    entries = render_paste_sections_form()
    if entries is None:
        st.divider()
        render_user_feedback(context={"mode": "paste"})
        return

    from savt.audit import run_audit_from_parsed
    from savt.paste_sections import build_parsed_from_pasted_sections, normalize_paste_entries
    from savt.section_audit import detect_document_sections

    filled = normalize_paste_entries(entries)
    if len(filled) < 2:
        st.error("Pegue al menos dos apartados con contenido antes de auditar.")
        st.divider()
        render_user_feedback(context={"mode": "paste"})
        return

    title = (st.session_state.get("paste_document_title") or "").strip()
    filename = "tesis-por-apartados.txt"
    if title:
        safe = _safe_slug(title) or "tesis"
        filename = f"{safe}.txt"

    try:
        parsed = build_parsed_from_pasted_sections(
            filled,
            filename=filename,
            document_title=title,
        )
    except ValueError as exc:
        st.error(str(exc))
        st.divider()
        render_user_feedback(context={"mode": "paste"})
        return

    config.resolve_for_document(parsed.get("full_text", ""), parsed.get("page_estimate", 0))
    detected = detect_document_sections(parsed)
    st.session_state["parsed_doc"] = parsed
    st.session_state["detected_sections"] = detected
    st.session_state["resolved_config"] = config
    st.session_state["paste_doc_name"] = filename

    progress_bar = st.progress(0.0)
    status_box = st.empty()

    def on_progress(phase: str, detail: str, fraction: float, payload: dict | None = None) -> None:
        progress_bar.progress(min(max(fraction, 0.0), 1.0))
        status_box.markdown(f"**{phase}** — {detail}")

    try:
        with st.spinner("Auditando los apartados pegados…"):
            report = run_audit_from_parsed(
                parsed,
                filename=filename,
                config=config,
                on_progress=on_progress,
            )
    except Exception as exc:
        st.error("La auditoría de apartados pegados falló. Puede corregir el texto y reintentar.")
        st.exception(exc)
        st.divider()
        render_user_feedback(context={"filename": filename, "mode": "paste"})
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
    st.session_state["profile_id"] = config.profile_id
    st.rerun()


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


def _depth_label_es(raw: str | None) -> str:
    from savt.content_quality import DEPTH_STATUS_LABELS

    value = (raw or "").strip().lower()
    if value in DEPTH_STATUS_LABELS:
        return DEPTH_STATUS_LABELS[value]
    mapping = {
        "conforme": "Conforme",
        "parcialmente conforme": "Parcialmente conforme",
        "no conforme": "No conforme",
        "no detectado": "No detectado",
    }
    return mapping.get(value, raw or "—")


def _clean_cell(value) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return "—"
    return text


def _jury_apartado_rows(dashboard: dict) -> tuple[list[dict], int, int]:
    """
    Apartados académicos para jurados: extensión y % sobre el cuerpo (bibliografía aparte).
    """
    from savt.chapter_reviews import SECTION_TITLES

    content = dashboard.get("content_dashboard") or {}
    total_body = int(content.get("total_body_words") or 0)
    bib_words = int(content.get("bibliography_words") or 0)
    if not bib_words:
        bib_words = int((dashboard.get("canonical_words") or {}).get("bibliografia") or 0)

    by_role = {s.get("role"): s for s in (content.get("sections") or []) if s.get("role")}

    jury_roles = (
        "introduccion",
        "objetivos",
        "marco_teorico",
        "metodologia",
        "resultados",
        "discusion",
        "conclusiones",
    )
    rows: list[dict] = []
    denom = max(total_body, 1)
    for role in jury_roles:
        label = SECTION_TITLES.get(role, role.replace("_", " ").title())
        sec = by_role.get(role) or {}
        words = int(sec.get("words") or 0)
        pct = sec.get("percent_label")
        if not pct and words:
            pct = f"{round(words * 100 / denom, 1):.1f}%"
        elif not words:
            pct = "—"
        rows.append({"Apartado": label, "Palabras": words, "% del cuerpo": pct})

    if bib_words:
        total_doc = max(total_body + bib_words, 1)
        rows.append(
            {
                "Apartado": SECTION_TITLES["bibliografia"],
                "Palabras": bib_words,
                "% del cuerpo": f"{round(bib_words * 100 / total_doc, 1):.1f}%",
            }
        )

    return rows, total_body, bib_words


def render_structure_and_checklist(dashboard: dict) -> None:
    """1) Apartados académicos + checklist (vista para jurados)."""
    detected = dashboard.get("detected_sections") or []
    model = dashboard.get("document_model") or {}
    chapters = model.get("chapters") or []
    thesis_type = dashboard.get("thesis_type") or "clasica"
    checklist = dashboard.get("checklist") or {}
    reviews = {r.get("key"): r for r in (dashboard.get("chapter_reviews") or [])}

    st.markdown("## 1. Estructura del documento y checklist")
    st.caption(
        "Extensión por **apartado académico** (lo que evalúan los jurados) "
        "y estado del checklist."
    )

    apartado_rows, total_body, bib_words = _jury_apartado_rows(dashboard)
    st.markdown("### Apartados detectados")
    if apartado_rows:
        for idx, row in enumerate(apartado_rows):
            c1, c2, c3 = st.columns([2.2, 1, 1])
            with c1:
                st.markdown(f"**{row['Apartado']}**")
            with c2:
                st.markdown(f"{int(row['Palabras']):,} palabras")
            with c3:
                st.markdown(str(row["% del cuerpo"]))
            if idx < len(apartado_rows) - 1:
                st.markdown(
                    "<hr style='margin:0.35rem 0;border:none;border-top:1px solid #eee'/>",
                    unsafe_allow_html=True,
                )
        classified = sum(int(r["Palabras"]) for r in apartado_rows if r["Apartado"] != "Bibliografía")
        st.caption(
            f"**Cuerpo:** {total_body:,} palabras · "
            f"**Clasificado en apartados:** {classified:,} · "
            f"**Bibliografía:** {bib_words:,} palabras."
        )
        zero_important = [
            r["Apartado"]
            for r in apartado_rows
            if int(r["Palabras"]) == 0
            and any(
                key in str(r["Apartado"]).lower()
                for key in ("marco", "objetivo", "introduc", "conclus")
            )
        ]
        if zero_important:
            st.warning(
                "**Apartados en 0 palabras:** "
                + ", ".join(zero_important)
                + ". Suele ocurrir si en la confirmación del índice quedaron como "
                "**«Otro / sin clasificar»** o el título no coincide con el PDF. "
                "Pulse **↩ Revisar estructura y reauditar**, asigne p. ej. "
                "«Revisión de literatura / Antecedentes» → **Marco teórico** "
                "y «Objetivos / Hipótesis / Justificación» → **Pregunta, objetivos e hipótesis**."
            )
        st.caption(
            "Los porcentajes del cuerpo se calculan sobre el total de palabras del texto principal "
            "(sin bibliografía). El % de bibliografía es sobre cuerpo + bibliografía."
        )
    else:
        st.warning("No se pudieron estimar apartados académicos.")

    chapter_rows = []
    if chapters:
        total = max(sum(int(c.get("words") or 0) for c in chapters), 1)
        for idx, chapter in enumerate(chapters, start=1):
            words = int(chapter.get("words") or 0)
            pct = round(words * 100 / total, 1)
            chapter_rows.append(
                {
                    "N°": idx,
                    "Capítulo": chapter.get("title") or "—",
                    "Palabras": words,
                    "%": f"{pct:.1f}%",
                }
            )
    elif detected and thesis_type != "compendio":
        for idx, item in enumerate(detected, start=1):
            chapter_rows.append(
                {
                    "N°": item.get("order", idx),
                    "Capítulo": item.get("path") or item.get("detected_as") or item.get("title") or "—",
                    "Palabras": item.get("words", 0),
                    "%": item.get("percent_label", "—"),
                }
            )

    tree = dashboard.get("structure_tree") or []
    if chapter_rows or tree:
        with st.expander("Capítulos del PDF (detalle estructural)", expanded=False):
            if chapter_rows:
                for row in chapter_rows:
                    title = str(row["Capítulo"])
                    st.markdown(
                        f"**{row['N°']}.** {title} — "
                        f"{int(row['Palabras']):,} palabras ({row['%']})"
                    )
                st.caption(
                    f"**{len(chapter_rows)}** capítulos · "
                    f"**{sum(int(r['Palabras']) for r in chapter_rows):,}** palabras."
                )
            if tree:
                st.markdown("**Subtítulos por capítulo**")
                for node in tree:
                    st.markdown(f"**{node.get('title')}** — {int(node.get('words') or 0):,} palabras")
                    for child in node.get("children") or []:
                        st.markdown(
                            f"- {child.get('title')} ({int(child.get('words') or 0):,} palabras)"
                        )

    st.markdown("### Checklist académico")
    st.markdown(f"**Estado general:** {checklist.get('status', '—')}")
    items = checklist.get("items") or []
    if not items:
        st.info("No hay checklist disponible.")
        return

    for idx, item in enumerate(items):
        key = item.get("section_key") or ""
        review = reviews.get(key) or {}
        title = review.get("title") or (item.get("label") or "—").split(" — ")[0].replace(" completo", "")
        if item.get("ok"):
            estado = "Completo"
        elif item.get("partial"):
            estado = "Revisión parcial"
        else:
            estado = "Requiere revisión"
        resumen = (review.get("summary") or "").strip() or "—"
        col_label, col_text = st.columns([1, 2.2], gap="medium")
        with col_label:
            st.markdown(f"**{title}**")
            st.caption(estado)
        with col_text:
            st.markdown(resumen)
            missing = review.get("missing") or []
            partial_items = review.get("partial_items") or []
            if missing or partial_items:
                from savt.chapter_reviews import CHECK_LABELS

                labels = [CHECK_LABELS.get(x, x) for x in (missing + partial_items)]
                st.caption("Elementos: " + "; ".join(labels))
            if review.get("why"):
                st.markdown(f"**Por qué importa:** {review['why']}")
            if review.get("how_to_fix"):
                st.markdown(f"**Cómo corregir:** {review['how_to_fix']}")
            elif item.get("ok"):
                st.caption(
                    "Completo según detección automática: el director debe confirmar "
                    "profundidad argumentativa y coherencia del apartado."
                )
        if idx < len(items) - 1:
            st.divider()


def render_evaluation_and_findings(dashboard: dict) -> None:
    """2) Apartados a corregir + hallazgos prioritarios (fusionados)."""
    reviews = dashboard.get("chapter_reviews") or []
    warnings = dashboard.get("warnings_list") or []

    st.markdown("## 2. Evaluación por apartados y hallazgos")
    st.caption(
        "Críticas y cómo corregir los apartados que no están completos, "
        "más alertas prioritarias que no se limitan al checklist."
    )

    pending = [r for r in reviews if not r.get("ok")]
    ok_count = sum(1 for r in reviews if r.get("ok"))

    if reviews:
        st.markdown(
            f"**Resumen:** {ok_count} completos · {len(pending)} con observaciones"
        )

    if not pending:
        st.success("Todos los apartados evaluados están completos según la detección automática.")
    else:
        st.markdown("### Qué revisar y cómo corregir")
        for review in pending:
            status = _review_status_label(review)
            with st.expander(f"{review.get('title')} — {status}", expanded=True):
                if review.get("summary"):
                    st.markdown(f"**Qué encontró SAVT:** {review['summary']}")
                missing = review.get("missing") or []
                partial_items = review.get("partial_items") or []
                if missing or partial_items:
                    from savt.chapter_reviews import CHECK_LABELS

                    labels = [
                        CHECK_LABELS.get(x, x) for x in (missing + partial_items)
                    ]
                    st.markdown("**Elementos a revisar:** " + "; ".join(labels))
                if review.get("why"):
                    st.markdown(f"**Por qué importa:** {review['why']}")
                if review.get("how_to_fix"):
                    st.info(f"**Cómo corregir:** {review['how_to_fix']}")
                else:
                    st.caption(
                        "Si el apartado está marcado como completo, igual conviene "
                        "releerlo con el director: SAVT valida presencia y marcadores, no calidad argumentativa."
                    )

    st.markdown("### Hallazgos prioritarios")
    if not warnings:
        st.success("No hay advertencias prioritarias adicionales.")
        return

    # Evitar repetir el mismo tema ya abierto arriba (mismo título de apartado)
    pending_titles = {(r.get("title") or "").lower() for r in pending}
    shown = 0
    for item in warnings:
        title = str(item.get("title") or "Hallazgo")
        # Seguir mostrando hallazgos concretos (DOI, etc.) aunque el área se repita
        shown += 1
        st.markdown(f"**{shown}. {title}**")
        st.caption(_clean_cell(item.get("gravity")))
        detail = item.get("detail")
        if detail:
            st.write(str(detail)[:350])
        if shown >= 10:
            break
    _ = pending_titles  # reserved for future smarter dedupe


def render_extra_evidence(dashboard: dict) -> None:
    """3) Citas y bibliografía con métricas claras (apariciones ≠ refs distintas ≠ entradas)."""
    from savt.section_audit import section_audit_ui_rows
    from savt.ui_labels import citation_reading_summary

    st.markdown("## 3. Citas por capítulo y bibliografía")
    recon = dashboard.get("citation_reconciliation") or {}
    bib = dashboard.get("bibliography_dashboard") or {}
    details = bib.get("details") or {}

    total_bib = bib.get("total_refs") or details.get("total_refs") or 0
    distinct = recon.get("document_unique_cited")
    if distinct is None:
        distinct = bib.get("citations_found") or 0
    appearances = recon.get("body_occurrences")
    if appearances is None:
        appearances = recon.get("sum_occurrences") or 0
    uncited = recon.get("uncited_references")
    if uncited is None:
        uncited = max(0, int(total_bib or 0) - int(distinct or 0))
    unmatched = bib.get("unmatched_citations") or recon.get("unmatched_citations") or 0

    text_unique = recon.get("text_unique_raw")
    if text_unique is None:
        text_unique = distinct
    text_unique = int(text_unique or 0)
    distinct = int(distinct or 0)
    appearances = int(appearances or 0)
    uncited = int(uncited or 0)
    unmatched = int(unmatched or 0)

    st.info(citation_reading_summary(recon, total_refs=int(total_bib or 0)))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Apariciones en el texto", appearances)
    m2.metric("Fuentes únicas (texto)", text_unique)
    m3.metric("Entradas bib. citadas", distinct)
    m4.metric("Entradas en bibliografía", total_bib)

    st.markdown("### Por capítulo")
    st.caption(
        "Por capítulo: **Fuentes únicas** = autor-año distintos en ese tramo. "
        "En la fila **TOTAL**, **Fuentes únicas** es el total del documento y "
        "**Bib. emparejadas** cuántas entradas de la lista final están citadas."
    )
    raw_rows = recon.get("reconciliation_rows") or []
    display_rows = []
    for row in raw_rows:
        apartado = _clean_cell(row.get("Apartado"))
        if apartado == "—":
            continue
        tipo = _clean_cell(row.get("Tipo")) or "Apartado"
        display_rows.append(
            {
                "Apartado": apartado,
                "Rol": _clean_cell(row.get("Rol académico")),
                "Veces citadas": _clean_cell(row.get("Apariciones cita")),
                "Fuentes únicas": _clean_cell(row.get("N° refs distintos")),
                "Bib. emparejadas": _clean_cell(row.get("Refs bib. emparejadas", "—")),
                "Tipo": tipo,
            }
        )
    if display_rows:
        st.dataframe(display_rows, hide_index=True, use_container_width=True)
    for note in recon.get("notes") or []:
        st.caption(note)

    audits = dashboard.get("section_audits") or []
    ui_rows = section_audit_ui_rows(audits)
    if ui_rows:
        with st.expander("Estado académico por capítulo", expanded=False):
            st.dataframe(ui_rows, hide_index=True, use_container_width=True)

    st.markdown("### Bibliografía — cobertura")
    coverage = bib.get("coverage") or details.get("coverage") or "—"
    doi_bad = len(details.get("doi_invalid") or [])
    doi_miss = len(details.get("doi_not_resolved") or [])
    out_period = bib.get("out_of_period") or 0
    period_start = details.get("period_start")

    st.markdown(
        f"**Estilo:** {_clean_cell(bib.get('style') or details.get('style') or 'APA')} · "
        f"**Cobertura:** {_clean_cell(coverage)}"
    )
    if unmatched:
        st.caption(f"Citas del texto sin emparejar con la bibliografía: **{unmatched}**")

    reasons: list[str] = []
    if coverage == "requiere revisión":
        if doi_miss:
            reasons.append(
                f"**Por qué la cobertura es insuficiente:** {doi_miss} DOI no se encontraron en Crossref "
                "(mal tipados, incompletos o retirados)."
            )
        if doi_bad:
            reasons.append(f"**DOI inválidos:** {doi_bad} entradas con formato incorrecto.")
        if unmatched and unmatched > 5:
            reasons.append(
                f"**Citas sin entrada:** {unmatched} citas del texto no coinciden con la bibliografía."
            )
        if not reasons:
            reasons.append(
                "**Por qué requiere revisión:** no se pudo verificar la consistencia "
                "citas ↔ bibliografía ↔ DOI."
            )
    if out_period:
        period_txt = f" (desde {period_start})" if period_start else ""
        reasons.append(
            f"**Antigüedad:** {out_period} referencias anteriores al período metodológico detectado{period_txt}."
        )
    for line in reasons:
        st.markdown(line)

    bib_review = next(
        (r for r in (dashboard.get("chapter_reviews") or []) if r.get("key") == "bibliografia"),
        None,
    )
    if bib_review:
        if bib_review.get("summary"):
            st.write(bib_review["summary"])
        if bib_review.get("why"):
            st.markdown(f"**Por qué importa:** {bib_review['why']}")
        if bib_review.get("how_to_fix"):
            st.info(f"**Cómo corregir:** {bib_review['how_to_fix']}")
        issues = bib_review.get("issues") or []
        if issues:
            st.markdown("**Hallazgos concretos:**")
            for issue in issues:
                st.markdown(f"- {_clean_cell(issue)}")


def render_executive_report(dashboard: dict, report, base_name: str) -> None:
    """Pantalla principal alineada a las hojas del Excel SAVT."""
    from savt.ui_labels import citation_reading_summary

    st.markdown("## Resultado de la auditoría")
    st.caption("Equivalente a la hoja «Resumen» del Excel.")
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

    bib = dashboard.get("bibliography_dashboard") or {}
    recon = dashboard.get("citation_reconciliation") or {}
    total_bib = int(bib.get("total_refs") or recon.get("total_references") or 0)
    text_unique = int(recon.get("text_unique_raw") or recon.get("document_unique_cited") or 0)
    bib_used = int(recon.get("document_unique_cited") or bib.get("citations_found") or 0)
    appearances = int(recon.get("body_occurrences") or 0)

    meta1, meta2, meta3, meta4 = st.columns(4)
    meta1.metric("Palabras (cuerpo)", report.word_count if report else "—")
    meta2.metric(
        "Apariciones de cita",
        appearances or "—",
        help="Veces que aparece una cita en el texto (la misma fuente puede contarse varias veces).",
    )
    meta3.metric(
        "Fuentes únicas en el texto",
        text_unique or "—",
        help="Autores-año distintos detectados en el cuerpo; cada fuente cuenta una sola vez.",
    )
    meta4.metric(
        "Bibliografía citada",
        f"{bib_used} / {total_bib}" if total_bib else bib_used,
        help="Entradas de la lista bibliográfica que están citadas al menos una vez.",
    )
    if recon:
        st.caption(citation_reading_summary(recon, total_refs=total_bib))
    st.caption(
        f"Errores críticos: **{dashboard.get('errors', 0)}** · "
        f"Advertencias: **{dashboard.get('warnings', 0)}**"
    )

    st.divider()
    render_structure_and_checklist(dashboard)
    st.divider()
    render_evaluation_and_findings(dashboard)
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
    """Compatibilidad."""
    render_structure_and_checklist(dashboard)


def render_document_chapters(dashboard: dict) -> None:
    """Compatibilidad con llamadas antiguas."""
    render_structure_and_checklist(dashboard)


def render_structure_confirmation(sections: list[dict], structure_source: str = "") -> dict | None:
    """
    Paso obligatorio: el usuario contrasta el índice, tilda cada apartado y puede agregar otros.
    Sin confirmación explícita no se audita.
    """
    import pandas as pd

    from savt.structure_confirm import (
        build_index_confirmation_rows,
        confirmation_from_index_editor,
        role_options,
        structure_confidence_summary,
    )

    st.markdown("## 2. Confirme el índice de su tesis")
    st.info(
        "**Antes de auditar**, abra el **índice / tabla de contenidos** del PDF y "
        "marque aquí cada apartado que realmente existe. "
        "Si su tesis usa otro nombre (p. ej. «Revisión de literatura» en lugar de «Marco teórico»), "
        "escriba ese título y asigne el apartado académico. "
        "Si falta uno, **agregue una fila** al final de la tabla."
    )

    if structure_source:
        source_label = {
            "index": "índice del documento",
            "capitulos": "capítulos del cuerpo (tesis por compendio)",
            "headings": "encabezados del cuerpo",
            "confirmed": "confirmación previa",
            "manual": "estructura manual",
        }.get(structure_source, structure_source)
        st.caption(
            f"Propuesta automática (solo ayuda): fuente **{source_label}**. "
            "Usted decide qué tildar según el índice real."
        )

    summary = structure_confidence_summary(sections or [])
    if sections and summary.get("needs_review"):
        st.warning(
            f"La detección automática tiene {summary['low']} apartado(s) dudoso(s). "
            "Contraste con el índice antes de continuar."
        )
    elif not sections:
        st.warning(
            "No se detectó una estructura clara. Complete la tabla con los títulos "
            "del índice (marque «Presente» y escriba el título)."
        )

    base_rows = build_index_confirmation_rows(sections or [])
    st.session_state["_index_confirm_meta"] = [
        {"_role_original": r.get("_role_original", "otros")} for r in base_rows
    ]
    df = pd.DataFrame(
        [
            {
                "Presente en el índice": r["Presente en el índice"],
                "Título en el índice": r["Título en el índice"],
                "Apartado académico": r["Apartado académico"],
                "Palabras (detección)": r["Palabras (detección)"],
            }
            for r in base_rows
        ]
    )

    st.markdown("### Apartados a confirmar")
    st.caption(
        "Marque **Presente en el índice**. Complete o corrija **Título en el índice** "
        "(tal como aparece en su tesis). Elija el **Apartado académico** "
        "(no deje el marco o los objetivos en «Otro / sin clasificar»). "
        "Use **+** al final de la tabla para agregar un apartado distinto."
    )
    edited = st.data_editor(
        df,
        hide_index=True,
        disabled=["Palabras (detección)"],
        column_config={
            "Presente en el índice": st.column_config.CheckboxColumn(
                "Presente en el índice",
                help="Tilde solo si ese apartado figura en el índice / cuerpo de su tesis.",
                default=False,
            ),
            "Título en el índice": st.column_config.TextColumn(
                "Título en el índice",
                help="Texto exacto o cercano al título del índice (ej. «2. REVISIÓN DE LITERATURA»).",
                width="large",
            ),
            "Apartado académico": st.column_config.SelectboxColumn(
                "Apartado académico",
                options=role_options(),
                required=True,
            ),
            "Palabras (detección)": st.column_config.TextColumn(
                "Palabras (detección)",
                help="Estimación automática previa; se recalcula al auditar con su confirmación.",
            ),
        },
        num_rows="dynamic",
        use_container_width=True,
        key="index_confirmation_editor",
    )

    present_count = 0
    if edited is not None:
        present_count = sum(1 for row in edited.to_dict("records") if row.get("Presente en el índice"))
    st.caption(f"Apartados marcados como presentes: **{present_count}** (mínimo 2 para auditar).")

    # Casilla junto al botón (no arriba, fuera de vista) y sin disabled=… (evita el cursor 🚫).
    reviewed = st.checkbox(
        "Confirmo que contrasté esta lista con el índice del documento",
        key="index_reviewed_checkbox",
    )

    confirm = st.button(
        "Confirmar índice y auditar",
        type="primary",
        key="btn_index_confirm_audit",
    )

    if confirm:
        if not reviewed:
            st.error(
                "Marque la casilla **«Confirmo que contrasté esta lista con el índice»** "
                "(justo arriba del botón) y vuelva a pulsar."
            )
            return None
        records = edited.to_dict("records") if edited is not None else []
        choice = confirmation_from_index_editor(records)
        if choice is None:
            st.error(
                "Marque al menos **dos** apartados como presentes y escriba su título "
                "(o deje el nombre del apartado académico). Agregue filas si faltan."
            )
            return None
        return choice

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

    st.session_state["input_mode"] = "paste"
    _run_paste_mode(config)
