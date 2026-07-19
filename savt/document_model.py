"""
Contrato oficial del documento estructurado (capa intermedia SAVT).

Principio: los evaluadores NO deben reinterpretar el PDF.
Leen este objeto JSON (o el dict equivalente en memoria).

Esquema mínimo (v1):

{
  "schema_version": "1.0",
  "thesis_type": "clasica" | "compendio",
  "structure_source": "index" | "capitulos" | "headings" | "manual" | "confirmed",
  "document": {
    "filename": "...",
    "title": "...",
    "word_count": 0,
    "page_estimate": 0,
    "language": "es"
  },
  "chapters": [
    {
      "id": "cap-1",
      "level": 1,
      "number": 1,
      "title": "CAPÍTULO 1: ...",
      "role": "marco_teorico",
      "words": 9215,
      "start": 0,
      "end": 100,
      "sections": [
        {
          "id": "cap-1-sec-1",
          "level": 2,
          "title": "INTRODUCCIÓN",
          "role": "introduccion",
          "words": 500,
          "start": 10,
          "end": 50
        }
      ]
    }
  ],
  "bibliography": {
    "style": "apa",
    "word_count": 0,
    "entry_count": 0
  },
  "meta": {
    "built_from": "structure_tree" | "index_sections" | "section_map"
  }
}
"""

from __future__ import annotations

import json
from typing import Any

from savt.word_stats import count_words


SCHEMA_VERSION = "1.0"


def _slug(text: str) -> str:
    import re
    import unicodedata

    folded = unicodedata.normalize("NFD", text or "")
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", folded.lower()).strip("-")
    return slug[:48] or "nodo"


def build_document_model(parsed: dict) -> dict[str, Any]:
    """
    Construye el contrato JSON a partir del resultado del parser/pipeline.
    Preferencia: structure_tree → index_sections → section_map.
    """
    thesis_type = str(parsed.get("thesis_type") or "clasica")
    structure_source = str(parsed.get("structure_source") or "headings")
    tree = parsed.get("structure_tree") or []
    built_from = "structure_tree"

    chapters: list[dict[str, Any]] = []
    if tree:
        for node in tree:
            num = node.get("chapter_num")
            title = str(node.get("title") or f"Capítulo {num}")
            cap_id = f"cap-{num}" if num is not None else f"cap-{_slug(title)}"
            sections = []
            for idx, child in enumerate(node.get("children") or [], start=1):
                ctitle = str(child.get("title") or f"Sección {idx}")
                sections.append(
                    {
                        "id": f"{cap_id}-sec-{idx}",
                        "level": int(child.get("level") or 2),
                        "title": ctitle,
                        "role": child.get("role") or "otros",
                        "words": int(child.get("words") or 0),
                        "start": child.get("start"),
                        "end": child.get("end"),
                        "kind": child.get("kind"),
                    }
                )
            chapters.append(
                {
                    "id": cap_id,
                    "level": 1,
                    "number": num,
                    "title": title,
                    "role": node.get("role") or "otros",
                    "words": int(node.get("words") or 0),
                    "start": node.get("start"),
                    "end": node.get("end"),
                    "sections": sections,
                }
            )
    else:
        built_from = "index_sections"
        index_sections = parsed.get("index_sections") or []
        if index_sections:
            for idx, item in enumerate(index_sections, start=1):
                title = str(item.get("title") or item.get("path") or f"Apartado {idx}")
                chapters.append(
                    {
                        "id": f"sec-{idx}-{_slug(title)}",
                        "level": int(item.get("level") or 1),
                        "number": item.get("chapter_num") or idx,
                        "title": title,
                        "role": item.get("role") or "otros",
                        "words": int(item.get("words") or 0),
                        "start": None,
                        "end": None,
                        "sections": [],
                    }
                )
        else:
            built_from = "section_map"
            section_map = parsed.get("section_map") or {}
            section_meta = parsed.get("section_meta") or {}
            for idx, (role, text) in enumerate(section_map.items(), start=1):
                titles = (section_meta.get(role) or {}).get("detected_titles") or [role]
                title = titles[0] if titles else role
                chapters.append(
                    {
                        "id": f"role-{idx}-{role}",
                        "level": 1,
                        "number": idx,
                        "title": str(title),
                        "role": role,
                        "words": count_words(text or ""),
                        "start": None,
                        "end": None,
                        "sections": [],
                    }
                )

    bibliography = parsed.get("bibliography") or {}
    entry_count = len(bibliography) if isinstance(bibliography, dict) else 0

    model: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "thesis_type": thesis_type,
        "structure_source": structure_source,
        "document": {
            "filename": parsed.get("filename") or "",
            "title": parsed.get("document_title") or "",
            "word_count": int(parsed.get("word_count") or 0),
            "page_estimate": int(parsed.get("page_estimate") or 0),
            "language": "es",
            "file_type": parsed.get("file_type") or "",
        },
        "chapters": chapters,
        "bibliography": {
            "style": parsed.get("citation_style") or "apa",
            "word_count": int(parsed.get("bibliography_word_count") or 0),
            "entry_count": entry_count,
        },
        "meta": {
            "built_from": built_from,
            "chapter_count": len(chapters),
            "section_count": sum(len(c.get("sections") or []) for c in chapters),
            "total_structured_words": sum(int(c.get("words") or 0) for c in chapters),
        },
    }
    return model


def document_model_to_json(model: dict[str, Any], *, indent: int = 2) -> str:
    """Serializa el contrato a JSON UTF-8."""
    return json.dumps(model, ensure_ascii=False, indent=indent)


def flatten_document_model_for_display(model: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Filas planas para UI/CSV a partir del contrato (solo nivel 1 por defecto).
    Los % se calculan sobre la suma de capítulos del modelo.
    """
    chapters = model.get("chapters") or []
    total = max(sum(int(c.get("words") or 0) for c in chapters), 1)
    rows: list[dict[str, Any]] = []
    for idx, chapter in enumerate(chapters, start=1):
        words = int(chapter.get("words") or 0)
        pct = round(words * 100 / total, 1)
        title = str(chapter.get("title") or "—")
        rows.append(
            {
                "role": chapter.get("role") or "otros",
                "title": title,
                "detected_as": title,
                "words": words,
                "percent": pct,
                "percent_label": f"{pct:.1f}%",
                "order": idx,
                "page": str(chapter.get("number") or ""),
                "level": int(chapter.get("level") or 1),
                "path": title,
                "source": "document_model",
                "node_id": chapter.get("id"),
            }
        )
    return rows


def ensure_document_model(parsed: dict) -> dict[str, Any]:
    """Garantiza parsed['document_model'] y lo devuelve."""
    model = parsed.get("document_model")
    if isinstance(model, dict) and model.get("schema_version"):
        return model
    model = build_document_model(parsed)
    parsed["document_model"] = model
    return model
