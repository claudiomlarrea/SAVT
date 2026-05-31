from __future__ import annotations

import re
from typing import Any

from savt.bibliography_styles import apa_keys_match
from savt.citations import is_reference_topical, _topic_keywords
from savt.models import Finding, ReferenceEntry
from savt.references import validate_doi

DOI_HELP = {
    "invalid": (
        "**DOI inválido:** el identificador está mal escrito o no sigue el formato internacional "
        "(debe comenzar con `10.`). Crossref no puede buscarlo."
    ),
    "not_resolved": (
        "**DOI no resuelto:** el formato es correcto pero Crossref no encuentra ese DOI. "
        "Puede estar desactualizado, ser erróneo o pertenecer a un registro no indexado."
    ),
    "network": (
        "**No verificado por red:** no se pudo consultar Crossref (conexión, proxy o firewall). "
        "No implica que la referencia sea falsa; conviene verificar manualmente."
    ),
    "year_mismatch": (
        "**Año distinto al registrado:** el año entre paréntesis en su bibliografía no coincide "
        "con el año de publicación registrado en Crossref para ese DOI."
    ),
}


def _ref_summary(num: int, ref: ReferenceEntry, max_len: int = 200) -> str:
    text = ref.raw[:max_len] + ("…" if len(ref.raw) > max_len else "")
    doi_part = f" | DOI: https://doi.org/{ref.doi}" if ref.doi else ""
    url_match = re.search(r"https?://\S+", ref.raw)
    url_part = f" | URL: {url_match.group(0)[:80]}" if url_match and not ref.doi else ""
    return f"Ref. {num} ({ref.year or 's/a'}): {text}{doi_part}{url_part}"


def _plausible_year(year: str) -> bool:
    return year.isdigit() and 1900 <= int(year) <= 2030


def analyze_unmatched_apa(parsed: dict, bibliography: dict[int, ReferenceEntry]) -> list[dict]:
    bib_keys = {ref.key for ref in bibliography.values() if ref.key}
    raw_map: dict[str, list[str]] = {}
    for key, paragraph in parsed.get("citation_contexts_apa", []):
        for match in re.finditer(r"\(([^()]*?\d{4}[a-z]?[^()]*?)\)", paragraph):
            inner = match.group(1).strip()
            if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúñ]{3}.*,\s*\d{4}", inner):
                continue
            from savt.bibliography_styles import apa_citation_key

            if apa_citation_key(inner) == key:
                raw_map.setdefault(key, [])
                formatted = f"({inner})"
                if formatted not in raw_map[key]:
                    raw_map[key].append(formatted)

    items: list[dict] = []
    for key in sorted(parsed.get("cited_keys", set())):
        if apa_keys_match(key, bib_keys):
            continue
        author, year = key.split("|", 1) if "|" in key else (key, "")
        items.append(
            {
                "key": key,
                "citations_in_text": raw_map.get(key, [f"({author}, {year})"]),
                "hint": (
                    "Busque en bibliografía una entrada con ese apellido y año, o corrija la cita en el texto. "
                    "Revise variantes: 'et al.', apellidos compuestos, instituciones (CEPAL/ECLAC)."
                ),
            }
        )
    return items


def analyze_out_of_period(
    bibliography: dict[int, ReferenceEntry], body: str
) -> tuple[int, int | None, list[dict]]:
    year_range = re.search(r"(20\d{2})\s*[–-]\s*(20\d{2})", body)
    if not year_range:
        return 0, None, []
    start_year = int(year_range.group(1))
    end_year = int(year_range.group(2))
    items: list[dict] = []
    for num, ref in sorted(bibliography.items()):
        if ref.year and _plausible_year(ref.year) and int(ref.year) < start_year:
            items.append(
                {
                    "number": num,
                    "year": ref.year,
                    "summary": _ref_summary(num, ref),
                    "period_declared": f"{start_year}–{end_year}",
                }
            )
    return len(items), start_year, items


def analyze_off_topic(
    bibliography: dict[int, ReferenceEntry], parsed: dict
) -> list[dict]:
    keywords = _topic_keywords(parsed)
    items: list[dict] = []
    for num, ref in sorted(bibliography.items()):
        if not is_reference_topical(ref, keywords):
            items.append(
                {
                    "number": num,
                    "summary": _ref_summary(num, ref),
                    "reason": "No contiene términos clave inferidos del título/tema del trabajo.",
                }
            )
    return items


def analyze_doi_issues(
    bibliography: dict[int, ReferenceEntry],
    verify_online: bool,
    max_checks: int,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[Finding]]:
    findings: list[Finding] = []
    invalid: list[dict] = []
    not_resolved: list[dict] = []
    network: list[dict] = []
    year_mismatch: list[dict] = []

    if not verify_online:
        return invalid, not_resolved, network, year_mismatch, findings

    checked = 0
    for num, ref in sorted(bibliography.items()):
        if checked >= max_checks:
            break
        if not ref.doi:
            continue
        checked += 1
        doi_url = f"https://doi.org/{ref.doi}"
        ok, message, meta = validate_doi(ref.doi)

        if ok:
            crossref_year = meta.get("year", "")
            if (
                ref.year
                and _plausible_year(ref.year)
                and crossref_year
                and ref.year != crossref_year
            ):
                item = {
                    "number": num,
                    "doi": ref.doi,
                    "doi_url": doi_url,
                    "year_in_bibliography": ref.year,
                    "year_in_crossref": crossref_year,
                    "summary": _ref_summary(num, ref),
                }
                year_mismatch.append(item)
            continue

        item = {
            "number": num,
            "doi": ref.doi,
            "doi_url": doi_url,
            "summary": _ref_summary(num, ref),
            "message": message,
        }

        if message.startswith("NETWORK_ERROR"):
            network.append(item)
        elif "formato inválido" in message.lower():
            invalid.append(item)
        else:
            not_resolved.append(item)

    if invalid or not_resolved:
        lines = []
        for group, label in ((invalid, "Inválidos"), (not_resolved, "No resueltos")):
            for item in group[:15]:
                lines.append(f"{label}: Ref. {item['number']} — {item['doi_url']} — {item['message']}")
        findings.append(
            Finding(
                module="Referencias",
                severity="error",
                area="Bibliografía",
                title="DOI inválidos o no resueltos",
                detail=(
                    f"{len(invalid)} DOI con formato inválido; "
                    f"{len(not_resolved)} DOI no encontrados en Crossref."
                ),
                evidence="\n".join(lines[:20]),
                why="Un DOI erróneo impide verificar la autenticidad y localización del documento citado.",
                how_to_fix="Corrija cada DOI/URL o reemplace la referencia por una fuente verificable.",
            )
        )
    elif network:
        findings.append(
            Finding(
                module="Referencias",
                severity="warning",
                area="Bibliografía",
                title="DOI no verificados por conexión",
                detail=f"No se pudieron verificar {len(network)} DOI por problemas de red.",
                evidence="\n".join(
                    f"Ref. {i['number']}: {i['doi_url']}" for i in network[:10]
                ),
                why="Sin verificación online no se confirma validez del enlace.",
                how_to_fix="Verifique manualmente cada DOI en https://doi.org o reactive la validación online.",
            )
        )
    elif checked and not year_mismatch:
        findings.append(
            Finding(
                module="Referencias",
                severity="ok",
                area="Bibliografía",
                title="DOI verificados",
                detail=f"Se verificaron {checked} DOI en Crossref sin errores de formato o resolución.",
            )
        )

    if year_mismatch:
        findings.append(
            Finding(
                module="Referencias",
                severity="warning",
                area="Bibliografía",
                title="Año bibliográfico distinto al registrado en Crossref",
                detail=(
                    f"{len(year_mismatch)} referencias tienen un año distinto al publicado "
                    "según Crossref para el mismo DOI."
                ),
                evidence="\n".join(
                    f"Ref. {i['number']}: bibliografía {i['year_in_bibliography']} vs "
                    f"Crossref {i['year_in_crossref']} — {i['doi_url']}"
                    for i in year_mismatch[:15]
                ),
                why="Inconsistencias de año debilitan la precisión académica de la cita.",
                how_to_fix="Ajuste el año en la bibliografía al año de publicación oficial del DOI.",
            )
        )

    return invalid, not_resolved, network, year_mismatch, findings


def build_bibliography_details(
    parsed: dict,
    bibliography: dict[int, ReferenceEntry],
    verify_online: bool,
    max_checks: int,
) -> tuple[dict[str, Any], list[Finding]]:
    style = parsed.get("citation_style", "numbered")
    findings: list[Finding] = []

    unmatched_apa: list[dict] = []
    if style == "apa":
        unmatched_apa = analyze_unmatched_apa(parsed, bibliography)
        if unmatched_apa:
            lines = []
            for item in unmatched_apa[:15]:
                cites = ", ".join(item["citations_in_text"][:3])
                lines.append(f"Cita en texto: {cites} → clave detectada: {item['key']}")
            findings.append(
                Finding(
                    module="Bibliografía",
                    severity="warning",
                    area="Bibliografía",
                    title="Citas APA sin coincidencia exacta en bibliografía",
                    detail=(
                        f"{len(unmatched_apa)} citas autor-año del texto no tienen entrada "
                        "coincidente en bibliografía."
                    ),
                    evidence="\n".join(lines),
                    why="Las citas sin entrada bibliográfica debilitan la trazabilidad académica.",
                    how_to_fix="Revise cada cita listada y complete o corrija la referencia en bibliografía.",
                )
            )

    out_count, period_start, out_of_period = analyze_out_of_period(bibliography, parsed.get("body", ""))
    if out_of_period:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="warning" if len(out_of_period) >= 3 else "info",
                area="Bibliografía",
                title="Referencias anteriores al rango metodológico declarado",
                detail=(
                    f"{len(out_of_period)} referencias son anteriores a {period_start} "
                    f"(período declarado en metodología)."
                ),
                evidence="\n".join(i["summary"] for i in out_of_period[:15]),
                why="Referencias muy anteriores al período declarado pueden debilitar la pertinencia temporal.",
                how_to_fix="Justifique su inclusión o reemplace por fuentes del período metodológico.",
            )
        )

    off_topic = analyze_off_topic(bibliography, parsed)
    if off_topic and len(off_topic) > len(bibliography) * 0.15:
        findings.append(
            Finding(
                module="Bibliografía",
                severity="warning",
                area="Bibliografía",
                title="Referencias posiblemente ajenas al tema central",
                detail=f"{len(off_topic)} referencias no contienen términos clave del tema.",
                evidence="\n".join(i["summary"] for i in off_topic[:12]),
                why="Referencias ajenas al tema pueden interpretarse como relleno bibliográfico.",
                how_to_fix="Elimine referencias irrelevantes o vincúlelas explícitamente al argumento.",
            )
        )

    invalid, not_resolved, network, year_mismatch, doi_findings = analyze_doi_issues(
        bibliography, verify_online, max_checks
    )
    findings.extend(doi_findings)

    bib_keys = {ref.key for ref in bibliography.values() if ref.key}
    if style == "apa":
        unmatched_count = len(unmatched_apa)
    else:
        unmatched_count = len(parsed.get("cited_numbers", set()) - set(bibliography.keys()))

    coverage = "adecuada"
    if unmatched_count > 5 or invalid or not_resolved:
        coverage = "requiere revisión"
    elif unmatched_count or out_of_period or year_mismatch:
        coverage = "aceptable con observaciones"

    details = {
        "style": "APA" if style == "apa" else "Vancouver numerado",
        "total_refs": len(bibliography),
        "citations_found": len(parsed.get("cited_numbers") or parsed.get("cited_keys", set())),
        "unmatched_count": unmatched_count,
        "unmatched_apa": unmatched_apa,
        "out_of_period": out_of_period,
        "period_start": period_start,
        "off_topic": off_topic[:25],
        "off_topic_count": len(off_topic),
        "doi_invalid": invalid,
        "doi_not_resolved": not_resolved,
        "doi_network": network,
        "doi_year_mismatch": year_mismatch,
        "coverage": coverage,
        "doi_help": DOI_HELP,
    }
    return details, findings
