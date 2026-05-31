from __future__ import annotations

import re
from typing import Iterable

import requests

from savt.models import Finding, ReferenceEntry

CROSSREF_URL = "https://api.crossref.org/works/"
TIMEOUT = 8


def _normalize_doi(doi: str) -> str:
    doi = doi.strip().lower()
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    return doi.rstrip(".,;")


def validate_doi(doi: str) -> tuple[bool, str, dict]:
    doi = _normalize_doi(doi)
    if not doi.startswith("10."):
        return False, "DOI con formato inválido", {}
    try:
        response = requests.get(f"{CROSSREF_URL}{doi}", timeout=TIMEOUT)
        if response.status_code == 404:
            return False, "DOI no encontrado en Crossref", {}
        response.raise_for_status()
        payload = response.json().get("message", {})
        title = " ".join(payload.get("title") or [])[:180]
        year = ""
        for key in ("published-print", "published-online", "created"):
            parts = payload.get(key, {}).get("date-parts", [])
            if parts and parts[0]:
                year = str(parts[0][0])
                break
        return True, title or "DOI válido", {"year": year, "title": title}
    except requests.RequestException as exc:
        return False, f"NETWORK_ERROR: {exc}", {}


def validate_pmid(pmid: str) -> tuple[bool, str]:
    try:
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": pmid, "retmode": "json"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        result = response.json().get("result", {})
        item = result.get(pmid, {})
        if not item or item.get("error"):
            return False, "PMID no encontrado"
        return True, item.get("title", "PMID válido")
    except requests.RequestException as exc:
        return False, f"No se pudo verificar PMID: {exc}"


def audit_references(
    bibliography: dict[int, ReferenceEntry],
    verify_online: bool = True,
    max_checks: int = 25,
) -> list[Finding]:
    findings: list[Finding] = []
    if not bibliography:
        return findings

    without_doi = [n for n, ref in bibliography.items() if not ref.doi]
    if without_doi:
        findings.append(
            Finding(
                module="Referencias",
                severity="info",
                title="Referencias sin DOI detectable",
                detail=f"{len(without_doi)} entradas no incluyen DOI parseable.",
                evidence=f"Ejemplos: {without_doi[:10]}",
            )
        )

    if not verify_online:
        findings.append(
            Finding(
                module="Referencias",
                severity="info",
                title="Verificación en línea desactivada",
                detail="Active la validación online para comprobar DOI/PMID.",
            )
        )
        return findings

    invalid_dois: list[str] = []
    network_errors: list[str] = []
    checked = 0
    for num, ref in sorted(bibliography.items()):
        if checked >= max_checks:
            break
        if not ref.doi:
            continue
        checked += 1
        ok, message, meta = validate_doi(ref.doi)
        if ok:
            if ref.year and meta.get("year") and ref.year != meta.get("year"):
                findings.append(
                    Finding(
                        module="Referencias",
                        severity="warning",
                        title=f"Posible discrepancia de año en referencia {num}",
                        detail=f"Bibliografía: {ref.year}; Crossref: {meta.get('year')}",
                        evidence=ref.raw[:180],
                    )
                )
            continue
        if message.startswith("NETWORK_ERROR"):
            network_errors.append(f"[{num}] {ref.doi}")
        else:
            invalid_dois.append(f"[{num}] {ref.doi} → {message}")

    if invalid_dois:
        findings.append(
            Finding(
                module="Referencias",
                severity="error",
                title="DOI inválidos o no resueltos",
                detail="Al menos un DOI no existe o no pudo validarse en Crossref.",
                evidence="\n".join(invalid_dois[:10]),
            )
        )
    elif network_errors:
        findings.append(
            Finding(
                module="Referencias",
                severity="warning",
                title="No se pudo verificar DOI por conexión",
                detail=(
                    "La validación online falló por red, proxy o firewall. "
                    "Esto no implica que las referencias sean falsas."
                ),
                evidence="\n".join(network_errors[:10]),
            )
        )
    elif checked:
        findings.append(
            Finding(
                module="Referencias",
                severity="ok",
                title="DOI verificados",
                detail=f"Se verificaron {checked} DOI en Crossref sin errores.",
            )
        )

    return findings
