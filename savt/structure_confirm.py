"""Confirmación editable de apartados detectados antes de auditar."""

from __future__ import annotations

from savt.word_stats import CANONICAL_SECTION_ORDER, count_words

ROLE_LABELS: dict[str, str] = {role: label for role, label in CANONICAL_SECTION_ORDER}
ROLE_LABELS["bibliografia"] = "Bibliografía / referencias"
ROLE_LABELS["otros"] = "Otro / sin clasificar"
ROLE_LABELS["omitir"] = "No existe / omitir"

EDITABLE_ROLES: tuple[str, ...] = tuple(role for role, _ in CANONICAL_SECTION_ORDER) + (
    "bibliografia",
    "otros",
    "omitir",
)

CONFIDENCE_LABELS = {
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
}


def confidence_for_section(
    *,
    role: str,
    words: int,
    detected_as: str = "",
    source: str = "",
    structure_source: str = "",
) -> tuple[str, str]:
    """Devuelve (nivel, etiqueta) de confianza para un apartado detectado."""
    title = (detected_as or "").strip().lower()
    weak_titles = {
        "",
        "—",
        "detectado por contenido",
        role.replace("_", " "),
        ROLE_LABELS.get(role, "").lower(),
    }
    weak_title = title in weak_titles or "detectado por contenido" in title

    if source == "index" or structure_source == "index":
        if words >= 200 and not weak_title:
            return "high", CONFIDENCE_LABELS["high"]
        if words >= 80:
            return "medium", CONFIDENCE_LABELS["medium"]
        return "low", CONFIDENCE_LABELS["low"]

    if words >= 400 and not weak_title:
        return "high", CONFIDENCE_LABELS["high"]
    if words >= 150 and not weak_title:
        return "medium", CONFIDENCE_LABELS["medium"]
    if words >= 80:
        return "medium" if not weak_title else "low", (
            CONFIDENCE_LABELS["medium"] if not weak_title else CONFIDENCE_LABELS["low"]
        )
    return "low", CONFIDENCE_LABELS["low"]


def enrich_detected_sections(
    sections: list[dict],
    *,
    structure_source: str = "",
) -> list[dict]:
    """Añade confianza y campos de edición a la lista de apartados detectados."""
    enriched: list[dict] = []
    for item in sections:
        role = item.get("role") or "otros"
        words = int(item.get("words") or 0)
        level, label = confidence_for_section(
            role=role,
            words=words,
            detected_as=str(item.get("detected_as") or ""),
            source=str(item.get("source") or ""),
            structure_source=structure_source,
        )
        enriched.append(
            {
                **item,
                "role": role,
                "confidence": level,
                "confidence_label": label,
                "confirmed_role": role,
                "include": True,
            }
        )
    return enriched


def role_options() -> list[str]:
    return [ROLE_LABELS[role] for role in EDITABLE_ROLES]


def label_to_role(label: str) -> str:
    for role, name in ROLE_LABELS.items():
        if name == label:
            return role
    return "otros"


def editor_rows(sections: list[dict]) -> list[dict]:
    """Filas listas para st.data_editor."""
    rows: list[dict] = []
    for idx, item in enumerate(sections, start=1):
        role = item.get("confirmed_role") or item.get("role") or "otros"
        rows.append(
            {
                "N°": idx,
                "Incluir": bool(item.get("include", True)),
                "Detectado como": item.get("detected_as") or "—",
                "Apartado canónico": ROLE_LABELS.get(role, ROLE_LABELS["otros"]),
                "Confianza": item.get("confidence_label") or "—",
                "Palabras": int(item.get("words") or 0),
                "% del cuerpo": item.get("percent_label") or "—",
                "_role_original": item.get("role") or "otros",
                "_text_key": item.get("role") or f"otros_{idx}",
            }
        )
    return rows


def overrides_from_editor(rows: list[dict]) -> list[dict]:
    """Normaliza filas editadas a overrides {role_original, confirmed_role, include}."""
    overrides: list[dict] = []
    for row in rows:
        original = str(row.get("_role_original") or "otros")
        confirmed = label_to_role(str(row.get("Apartado canónico") or ROLE_LABELS["otros"]))
        overrides.append(
            {
                "role_original": original,
                "confirmed_role": confirmed,
                "include": bool(row.get("Incluir", True)),
                "detected_as": str(row.get("Detectado como") or ""),
                "words": int(row.get("Palabras") or 0),
            }
        )
    return overrides


def apply_section_overrides(parsed: dict, overrides: list[dict]) -> dict:
    """
    Reescribe section_map / section_meta / index_sections según confirmación del usuario.
    No regenera texto: reasigna roles canónicos sobre los bloques ya detectados.
    """
    if not overrides:
        return parsed

    section_map = dict(parsed.get("section_map") or {})
    section_meta = dict(parsed.get("section_meta") or {})
    role_texts, meta = {}, {}

    # Preferir el mapa canónico existente; si hay index_sections, usar sus textos.
    if parsed.get("structure_source") == "index" and parsed.get("index_sections"):
        for item in parsed["index_sections"]:
            role = item.get("role") or "otros"
            text = (parsed.get("section_map") or {}).get(role) or item.get("text") or ""
            if not text and role in section_map:
                text = section_map[role]
            role_texts.setdefault(role, "")
            if text and len(text) > len(role_texts[role]):
                role_texts[role] = text
            titles = [item.get("title") or role]
            meta.setdefault(role, {"detected_titles": titles})
    else:
        role_texts = dict(section_map)
        meta = dict(section_meta)

    # Fallback: textos del partition si el mapa está vacío.
    if not role_texts:
        from savt.word_stats import get_section_word_partition

        role_texts, meta = get_section_word_partition(parsed)

    new_map: dict[str, str] = {}
    new_meta: dict[str, dict] = {}
    remapped_index: list[dict] = []

    for override in overrides:
        if not override.get("include", True):
            continue
        confirmed = override.get("confirmed_role") or "otros"
        if confirmed in {"omitir", "otros"}:
            continue
        original = override.get("role_original") or confirmed
        text = role_texts.get(original) or role_texts.get(confirmed) or ""
        if not text and original in section_map:
            text = section_map[original]
        if not text.strip():
            continue

        if confirmed in new_map and len(text) <= len(new_map[confirmed]):
            # Conservar el bloque más largo si hay colisión de roles.
            pass
        else:
            if confirmed in new_map and new_map[confirmed].strip():
                # Concatenar si el usuario asignó dos bloques al mismo rol.
                if text not in new_map[confirmed]:
                    new_map[confirmed] = f"{new_map[confirmed].rstrip()}\n\n{text.strip()}"
            else:
                new_map[confirmed] = text.strip()

        detected_as = override.get("detected_as") or ROLE_LABELS.get(confirmed, confirmed)
        titles = list(new_meta.get(confirmed, {}).get("detected_titles") or [])
        if detected_as not in titles:
            titles.append(detected_as)
        new_meta[confirmed] = {
            **(meta.get(original) or meta.get(confirmed) or {}),
            "detected_titles": titles,
            "user_confirmed": True,
            "confidence": "high",
        }
        remapped_index.append(
            {
                "role": confirmed,
                "title": detected_as,
                "words": count_words(new_map[confirmed]),
                "page": (meta.get(original) or {}).get("index_page"),
            }
        )

    # Conservar bloques no editados que no fueron omitidos explícitamente.
    touched_originals = {o.get("role_original") for o in overrides}
    for role, text in role_texts.items():
        if role in touched_originals:
            continue
        if role in new_map or not text.strip():
            continue
        if role in ROLE_LABELS and role not in {"otros", "omitir"}:
            new_map[role] = text
            new_meta[role] = dict(meta.get(role) or {"detected_titles": [ROLE_LABELS[role]]})

    parsed = dict(parsed)
    parsed["section_map"] = new_map
    parsed["section_meta"] = new_meta
    parsed["structure_confirmed"] = True
    if remapped_index:
        # Recalcular porcentajes para vista.
        total = max(sum(item["words"] for item in remapped_index), 1)
        for item in remapped_index:
            pct = round(item["words"] * 100 / total, 1)
            item["percent"] = pct
            item["percent_label"] = f"{pct:.1f}%"
        parsed["index_sections"] = remapped_index
        if parsed.get("structure_source") != "index":
            parsed["structure_source"] = "confirmed"
    return parsed


def structure_confidence_summary(sections: list[dict]) -> dict:
    levels = [s.get("confidence") for s in sections]
    return {
        "total": len(sections),
        "high": sum(1 for c in levels if c == "high"),
        "medium": sum(1 for c in levels if c == "medium"),
        "low": sum(1 for c in levels if c == "low"),
        "needs_review": sum(1 for c in levels if c in {"low", "medium"}) > 0,
    }
