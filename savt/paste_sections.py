"""Modo SAVT: cargar la tesis pegando apartados (sin PDF/Word)."""

from __future__ import annotations

import re
from typing import Any

from savt.bibliography_styles import (
    detect_citation_style_with_body,
    parse_bibliography_by_style,
)
from savt.citations import extract_apa_citations, extract_cited_numbers, strip_embedded_bibliographies
from savt.document_model import ensure_document_model
from savt.parser import count_words, split_sections
from savt.word_stats import CANONICAL_SECTION_ORDER

# Campos fijos del formulario (id estable → rol / etiqueta).
PASTE_FIELD_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "introduccion",
        "role": "introduccion",
        "label": "Introducción",
        "help": "Planteamiento del tema o del problema, contexto y apertura del trabajo.",
        "height": 160,
        "required_hint": True,
    },
    {
        "id": "justificacion",
        "role": "justificacion",
        "label": "Justificación",
        "help": "Relevancia académica, social o institucional del estudio.",
        "height": 120,
    },
    {
        "id": "estado_del_arte",
        "role": "estado_del_arte",
        "label": "Estado del arte",
        "help": "Revisión de antecedentes y literatura previa (si está separado del marco).",
        "height": 160,
    },
    {
        "id": "marco_teorico",
        "role": "marco_teorico",
        "label": "Marco teórico",
        "help": "Marco conceptual, bases teóricas o revisión de literatura.",
        "height": 180,
        "required_hint": True,
    },
    {
        "id": "pregunta",
        "role": "pregunta",
        "label": "Pregunta de investigación",
        "help": "Pregunta central o preguntas específicas del estudio.",
        "height": 90,
    },
    {
        "id": "objetivo_general",
        "role": "objetivo_general",
        "label": "Objetivo general",
        "help": "Objetivo general del trabajo.",
        "height": 80,
        "required_hint": True,
    },
    {
        "id": "objetivos_especificos",
        "role": "objetivos_especificos",
        "label": "Objetivos específicos",
        "help": "Liste los objetivos específicos (uno por línea o numerados).",
        "height": 120,
        "required_hint": True,
    },
    {
        "id": "hipotesis",
        "role": "hipotesis",
        "label": "Hipótesis",
        "help": "Si el diseño lo incluye; deje vacío si no aplica.",
        "height": 90,
    },
    {
        "id": "metodologia",
        "role": "metodologia",
        "label": "Metodología / Materiales y métodos",
        "help": "Diseño, población, muestra, variables, procedimiento, instrumentos, etc.",
        "height": 180,
        "required_hint": True,
    },
    {
        "id": "resultados",
        "role": "resultados",
        "label": "Resultados",
        "help": "Hallazgos, tablas y figuras descritas.",
        "height": 180,
        "required_hint": True,
    },
    {
        "id": "discusion",
        "role": "discusion",
        "label": "Discusión",
        "help": "Interpretación, contraste con literatura, limitaciones e implicaciones.",
        "height": 160,
        "required_hint": True,
    },
    {
        "id": "conclusiones",
        "role": "conclusiones",
        "label": "Conclusiones",
        "help": "Cierre respecto de objetivos o pregunta; aportes y líneas futuras.",
        "height": 140,
        "required_hint": True,
    },
    {
        "id": "bibliografia",
        "role": "bibliografia",
        "label": "Bibliografía",
        "help": "Pegue el listado completo de referencias (APA, Vancouver u otro).",
        "height": 200,
        "required_hint": True,
    },
)

# Roles que el usuario puede asignar a un apartado extra.
EXTRA_ROLE_OPTIONS: tuple[tuple[str, str], ...] = tuple(
    (role, label) for role, label in CANONICAL_SECTION_ORDER
) + (
    ("justificacion", "Justificación"),
    ("estado_del_arte", "Estado del arte"),
    ("pregunta", "Pregunta de investigación"),
    ("hipotesis", "Hipótesis"),
    ("bibliografia", "Bibliografía / referencias"),
    ("otros", "Otro / sin clasificar"),
)

_MERGE_INTRO_IDS = ("introduccion", "justificacion")
_MERGE_MARCO_IDS = ("estado_del_arte", "marco_teorico")
_MERGE_OBJ_IDS = ("pregunta", "objetivo_general", "objetivos_especificos", "hipotesis")


def paste_field_specs() -> list[dict[str, Any]]:
    return [dict(spec) for spec in PASTE_FIELD_SPECS]


def extra_role_labels() -> dict[str, str]:
    return {role: label for role, label in EXTRA_ROLE_OPTIONS}


def _slug_title(title: str, fallback: str = "extra") -> str:
    folded = re.sub(r"[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ]+", "-", (title or "").strip().lower())
    folded = folded.strip("-")[:40]
    return folded or fallback


def _join_labeled(parts: list[tuple[str, str]]) -> str:
    chunks: list[str] = []
    for title, text in parts:
        text = (text or "").strip()
        if not text:
            continue
        chunks.append(f"{title.strip()}\n\n{text}")
    return "\n\n".join(chunks).strip()


def normalize_paste_entries(raw_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normaliza entradas del formulario: id, role, title, text."""
    labels = {spec["id"]: spec["label"] for spec in PASTE_FIELD_SPECS}
    role_by_id = {spec["id"]: spec["role"] for spec in PASTE_FIELD_SPECS}
    out: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw_entries or []):
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        entry_id = str(entry.get("id") or f"extra_{idx}").strip()
        role = str(entry.get("role") or role_by_id.get(entry_id) or "otros").strip() or "otros"
        title = str(entry.get("title") or labels.get(entry_id) or entry_id).strip()
        out.append(
            {
                "id": entry_id,
                "role": role,
                "title": title,
                "text": text,
                "words": count_words(text),
            }
        )
    return out


def build_parsed_from_pasted_sections(
    raw_entries: list[dict[str, Any]],
    *,
    filename: str = "tesis-por-apartados.txt",
    document_title: str = "",
) -> dict[str, Any]:
    """
    Construye un `parsed` compatible con `run_audit_from_parsed` a partir de textos pegados.

    - Arma body + bibliografía por separado.
    - Rellena section_map con roles canónicos (fusionando campos afines).
    - Marca structure_source=manual y structure_confirmed=True.
    """
    entries = normalize_paste_entries(raw_entries)
    if len(entries) < 2:
        raise ValueError(
            "Pegue al menos dos apartados con contenido (por ejemplo Introducción y Metodología)."
        )

    by_id = {e["id"]: e for e in entries}
    # También indexar por rol cuando hay extras con rol canónico.
    by_role: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_role.setdefault(entry["role"], []).append(entry)

    def _texts_for_ids(ids: tuple[str, ...]) -> list[tuple[str, str]]:
        parts: list[tuple[str, str]] = []
        for eid in ids:
            entry = by_id.get(eid)
            if entry:
                parts.append((entry["title"], entry["text"]))
        return parts

    def _texts_for_role(role: str) -> list[tuple[str, str]]:
        return [(e["title"], e["text"]) for e in by_role.get(role, [])]

    section_map: dict[str, str] = {}
    section_meta: dict[str, dict[str, Any]] = {}

    # Campos granulares (útiles para checks y UI).
    for entry in entries:
        if entry["role"] == "bibliografia":
            continue
        key = entry["id"] if entry["id"] in {s["id"] for s in PASTE_FIELD_SPECS} else entry["role"]
        # Evitar pisar un canónico con un extra: concatenar.
        if key in section_map:
            section_map[key] = (section_map[key] + "\n\n" + entry["text"]).strip()
        else:
            section_map[key] = entry["text"]
        meta = section_meta.setdefault(key, {"detected_titles": [], "source": "paste"})
        titles = meta.setdefault("detected_titles", [])
        if entry["title"] not in titles:
            titles.append(entry["title"])

    def _merge_ids_and_extra_role(ids: tuple[str, ...], role: str) -> str:
        parts = _texts_for_ids(ids)
        known_ids = set(ids)
        for entry in by_role.get(role, []):
            if entry["id"] in known_ids:
                continue
            parts.append((entry["title"], entry["text"]))
        return _join_labeled(parts)

    intro = _merge_ids_and_extra_role(_MERGE_INTRO_IDS, "introduccion")
    if intro:
        section_map["introduccion"] = intro

    marco = _merge_ids_and_extra_role(_MERGE_MARCO_IDS, "marco_teorico")
    if marco:
        section_map["marco_teorico"] = marco

    objetivos = _merge_ids_and_extra_role(_MERGE_OBJ_IDS, "objetivos")
    if objetivos:
        section_map["objetivos"] = objetivos

    for role in (
        "presentacion",
        "analisis_bibliometrico",
        "metodologia",
        "resultados",
        "discusion",
        "conclusiones",
    ):
        # Preferir el campo fijo del formulario; sumar extras con el mismo rol.
        parts: list[tuple[str, str]] = []
        fixed = by_id.get(role)
        if fixed:
            parts.append((fixed["title"], fixed["text"]))
        for entry in by_role.get(role, []):
            if fixed and entry["id"] == fixed["id"]:
                continue
            parts.append((entry["title"], entry["text"]))
        joined = _join_labeled(parts)
        if joined:
            section_map[role] = joined

    # Extras «otros»: conservar con clave única.
    for entry in entries:
        if entry["role"] != "otros":
            continue
        key = f"otros_{_slug_title(entry['title'], entry['id'])}"
        section_map[key] = entry["text"]
        section_meta[key] = {
            "detected_titles": [entry["title"]],
            "source": "paste",
            "role": "otros",
        }

    bib_entries = [e for e in entries if e["role"] == "bibliografia"]
    bib_text = _join_labeled([(e["title"], e["text"]) for e in bib_entries])
    if bib_text and not bib_text.upper().startswith("BIBLIOGRAF"):
        bib_text = "BIBLIOGRAFÍA\n" + bib_text

    body_blocks: list[str] = []
    index_sections: list[dict[str, Any]] = []
    for order, entry in enumerate(entries):
        if entry["role"] == "bibliografia":
            continue
        block = f"{entry['title']}\n\n{entry['text']}".strip()
        body_blocks.append(block)

    body = "\n\n".join(body_blocks).strip()
    if not body:
        raise ValueError("No hay texto de cuerpo: pegue apartados además de la bibliografía.")

    # Offsets en el body unido (para modelo de documento / auditorías por span).
    offset = 0
    body_order = 0
    for entry in entries:
        if entry["role"] == "bibliografia":
            continue
        block = f"{entry['title']}\n\n{entry['text']}".strip()
        start = body.find(block, offset)
        if start < 0:
            start = offset
        end = start + len(block)
        index_sections.append(
            {
                "title": entry["title"],
                "role": entry["role"] if entry["role"] != "otros" else "otros",
                "level": 1,
                "order": body_order,
                "start": start,
                "end": end,
                "words": entry["words"],
                "source": "paste",
            }
        )
        offset = end
        body_order += 1

    full_text = body
    if bib_text:
        full_text = f"{body}\n\n{bib_text}".strip()

    citation_style = detect_citation_style_with_body(body, bib_text)
    bibliography = parse_bibliography_by_style(bib_text, citation_style) if bib_text.strip() else {}

    body_for_cites = strip_embedded_bibliographies(body)
    citation_contexts_apa: list[tuple[str, str]] = []
    if citation_style == "apa":
        cited_keys, citation_contexts_apa = extract_apa_citations(body_for_cites)
        cited_numbers: set[int] = set()
    else:
        cited_numbers = extract_cited_numbers(
            body_for_cites,
            max_ref=max(bibliography.keys()) if bibliography else 500,
        )
        cited_keys = set()

    pregunta = (by_id.get("pregunta") or {}).get("text") or ""
    if not pregunta:
        for e in by_role.get("pregunta", []):
            pregunta = e["text"]
            break
    research_questions = [pregunta.strip()] if pregunta.strip() else []

    obj_general = (by_id.get("objetivo_general") or {}).get("text") or ""
    obj_esp = (by_id.get("objetivos_especificos") or {}).get("text") or ""
    objectives_parts = []
    if obj_general.strip():
        objectives_parts.append("Objetivo general\n" + obj_general.strip())
    if obj_esp.strip():
        objectives_parts.append("Objetivos específicos\n" + obj_esp.strip())
    objectives = "\n\n".join(objectives_parts).strip()
    if not objectives and section_map.get("objetivos"):
        objectives = section_map["objetivos"]

    conclusions = section_map.get("conclusiones") or ""

    word_count = count_words(body)
    bib_words = count_words(bib_text)
    page_estimate = max(1, round(word_count / 300))

    pipeline = [
        {
            "id": "paste",
            "title": "1. Carga por apartados",
            "status": "ok",
            "summary": f"{len(entries)} apartados pegados · {word_count:,} palabras en el cuerpo",
            "details": {"entries": len(entries), "words": word_count},
        },
        {
            "id": "sections",
            "title": "2. Mapa de apartados",
            "status": "ok",
            "summary": "Estructura definida por el usuario (sin detectar desde PDF)",
            "details": {"source": "paste", "sections": index_sections},
        },
        {
            "id": "bibliography",
            "title": "3. Bibliografía",
            "status": "ok" if len(bibliography) >= 3 else ("warning" if bib_text else "error"),
            "summary": (
                f"{len(bibliography)} referencias parseadas"
                if bibliography
                else ("Bibliografía pegada pero no parseable" if bib_text else "Sin bibliografía")
            ),
            "details": {
                "style": citation_style,
                "references": len(bibliography),
                "words": bib_words,
            },
        },
        {
            "id": "references",
            "title": "4. Citas en el cuerpo",
            "status": "ok",
            "summary": (
                f"Cuerpo: {len(cited_keys) or len(cited_numbers)} refs distintas · "
                f"Bibliografía: {len(bibliography)} entradas"
            ),
            "details": {
                "cited_keys": len(cited_keys),
                "cited_numbers": len(cited_numbers),
                "total": len(bibliography),
            },
        },
    ]

    title = (document_title or "").strip() or filename.rsplit(".", 1)[0]

    parsed: dict[str, Any] = {
        "filename": filename,
        "file_type": "paste",
        "document_title": title,
        "full_text": full_text,
        "body": body,
        "bibliography_text": bib_text,
        "bibliography": bibliography,
        "bibliography_for_parse": re.sub(
            r"^(?:\s*BIBLIOGRAF[IÍ]A\s*)", "", bib_text, flags=re.I
        ).strip(),
        "citation_style": citation_style,
        "cited_numbers": cited_numbers,
        "cited_keys": cited_keys,
        "citation_contexts_apa": citation_contexts_apa,
        "section_map": section_map,
        "section_meta": section_meta,
        "index_sections": index_sections,
        "index_entries": [],
        "structure_source": "manual",
        "structure_confirmed": True,
        "structure_tree": [],
        "thesis_type": "clasica",
        "index_layout": "paste",
        "input_mode": "paste",
        "paste_entries": entries,
        "sections": split_sections(body),
        "research_questions": research_questions,
        "objectives": objectives,
        "conclusions": conclusions,
        "word_count": word_count,
        "bibliography_word_count": bib_words,
        "page_estimate": page_estimate,
        "page_estimate_body_only": page_estimate,
        "pdf_page_count": None,
        "pdf_extraction": None,
        "topic_keywords": [],
        "pipeline": pipeline,
    }
    parsed["document_model"] = ensure_document_model(parsed)
    return parsed


def paste_entries_summary(entries: list[dict[str, Any]]) -> str:
    filled = normalize_paste_entries(entries)
    if not filled:
        return "Ningún apartado con texto todavía."
    bits = [f"{e['title']} ({e['words']:,} pal.)" for e in filled]
    return f"{len(filled)} apartados: " + "; ".join(bits[:8]) + ("…" if len(bits) > 8 else "")
