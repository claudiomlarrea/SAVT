from __future__ import annotations

import re

from savt.audit_config import AuditConfig
from savt.document_sections import extract_section, get_section_map
from savt.models import Finding
from savt.word_stats import CANONICAL_SECTION_ORDER, build_word_statistics, count_words, get_section_word_partition

CRITICAL_MARKERS = [
    "sin embargo",
    "no obstante",
    "por el contrario",
    "cabe señalar",
    "limitaciones de",
    "autores como",
    "según",
    "frente a",
    "en contraste",
    "critican",
    "cuestionan",
    "debate",
    "controversia",
]

HYPOTHESIS_PATTERNS = [
    r"hip[oó]tesis\s+(?:de\s+investigaci[oó]n|general|n[°º]?\s*\d)",
    r"hip[oó]tesis\s*:",
    r"se\s+plantea\s+la\s+hip[oó]tesis",
]

RESULTS_MARKERS = [
    "los resultados muestran",
    "se encontró",
    "se observó",
    "el análisis reveló",
    "los datos indican",
    "hallazgo",
    "figura",
    "tabla",
    "gráfico",
]

ROLE_DEPTH_RULES: dict[str, dict] = {
    "presentacion": {"min_words": 80},
    "introduccion": {"min_words": 120, "min_density": 0.2},
    "objetivos": {"min_words": 50},
    "analisis_bibliometrico": {"min_words": 400, "min_density": 0.3},
    "marco_teorico": {"min_words": 800, "min_density": 1.0, "min_critical": 2},
    "metodologia": {"min_words": 350, "min_density": 0.2},
    "resultados": {"min_words": 250, "min_result_markers": 2},
    "discusion": {"min_words": 450, "min_density": 0.6, "min_critical": 2},
    "conclusiones": {"min_words": 150, "min_critical": 1},
}

DEPTH_STATUS_LABELS = {
    "adequate": "Conforme",
    "partial": "Parcialmente conforme",
    "weak": "No conforme",
    "missing": "No detectado",
}

_DEPTH_RANK = {"missing": 0, "weak": 1, "partial": 2, "adequate": 3}

# Roles de profundidad alineados con el checklist de presentación.
CHECKLIST_ALIGNED_ROLES: dict[str, str] = {
    "introduccion": "introduccion",
    "objetivos": "objetivos",
    "marco_teorico": "marco_teorico",
    "metodologia": "metodologia",
    "resultados": "resultados",
    "discusion": "discusion",
    "conclusiones": "conclusiones",
}


def _count_citations(text: str) -> int:
    from savt.parser import count_numeric_citation_appearances

    cites = count_numeric_citation_appearances(text)
    cites += len(re.findall(r"\([A-ZÁÉÍÓÚÑ][^)]*,\s*\d{4}", text))
    return cites


def _section_metrics(text: str) -> dict:
    words = count_words(text)
    if words <= 0:
        return {
            "words": 0,
            "citation_count": 0,
            "citation_density": 0.0,
            "critical_markers": 0,
            "result_markers": 0,
        }
    lower = text.lower()
    critical = sum(1 for marker in CRITICAL_MARKERS if marker in lower)
    result_markers = sum(1 for marker in RESULTS_MARKERS if marker in lower)
    cites = _count_citations(text)
    density = round(cites / (words / 100), 2)
    return {
        "words": words,
        "citation_count": cites,
        "citation_density": density,
        "critical_markers": critical,
        "result_markers": result_markers,
    }


def _failed_depth_checks(role: str, metrics: dict) -> list[str]:
    """Indicadores no alcanzados, en lenguaje breve para el usuario."""
    rules = ROLE_DEPTH_RULES.get(role, {"min_words": 100})
    words = metrics["words"]
    if words <= 0:
        return ["apartado no detectado"]

    failed: list[str] = []
    min_words = rules.get("min_words", 100)
    if words < min_words:
        failed.append(f"extensión breve ({words} palabras; mínimo ~{min_words})")

    if "min_density" in rules:
        min_cites = int(rules["min_density"] * words / 100)
        if metrics["citation_count"] < min_cites:
            cites = metrics["citation_count"]
            if cites == 0:
                failed.append("sin citas bibliográficas detectadas")
            else:
                failed.append(
                    f"pocas citas para la extensión ({cites}; se esperaban ≥{max(min_cites, 1)})"
                )

    if "min_critical" in rules and metrics["critical_markers"] < rules["min_critical"]:
        failed.append(
            f"pocos marcadores de análisis crítico ({metrics['critical_markers']}; "
            f"mínimo {rules['min_critical']})"
        )

    if "min_result_markers" in rules and metrics["result_markers"] < rules["min_result_markers"]:
        failed.append("pocos indicadores de presentación de hallazgos")

    return failed


def _depth_reason(role: str, metrics: dict, status: str) -> str:
    if status in {"adequate", "missing"}:
        return ""
    failed = _failed_depth_checks(role, metrics)
    if status == "partial" and failed:
        return f"{failed[0].capitalize()}."
    if status == "weak":
        if failed:
            return f"{'; '.join(failed[:2]).capitalize()}."
        return "No alcanza los umbrales mínimos del apartado."
    return ""


def _assess_section_depth(role: str, metrics: dict) -> str:
    rules = ROLE_DEPTH_RULES.get(role, {"min_words": 100})
    words = metrics["words"]
    if words <= 0:
        return "missing"
    if role == "introduccion" and words >= 80:
        # Apartado sin título explícito pero con planteamiento/pregunta detectable.
        checks = ["min_words"]
        passed = 1 if words >= rules.get("min_words", 0) else 0
        if "min_density" in rules:
            checks.append("min_density")
            min_cites = rules["min_density"] * words / 100
            if metrics["citation_count"] >= min_cites:
                passed += 1
        if passed == len(checks):
            return "adequate"
        return "partial"
    if words < rules.get("min_words", 100) * 0.5:
        return "weak"

    checks = ["min_words"]
    passed = 1 if words >= rules.get("min_words", 0) else 0

    if "min_density" in rules:
        checks.append("min_density")
        min_cites = rules["min_density"] * words / 100
        if metrics["citation_count"] >= min_cites:
            passed += 1
    if "min_critical" in rules:
        checks.append("min_critical")
        if metrics["critical_markers"] >= rules["min_critical"]:
            passed += 1
    if "min_result_markers" in rules:
        checks.append("min_result_markers")
        if metrics["result_markers"] >= rules["min_result_markers"]:
            passed += 1

    total = len(checks)
    if passed == total:
        return "adequate"
    if passed >= max(1, total - 1):
        return "partial"
    return "weak"


def build_section_depth_analysis(parsed: dict) -> list[dict]:
    role_texts, section_meta = get_section_word_partition(parsed)

    rows: list[dict] = []

    for role, label in CANONICAL_SECTION_ORDER:
        text = role_texts.get(role, "")
        metrics = _section_metrics(text)
        depth_status = _assess_section_depth(role, metrics)
        detected = section_meta.get(role, {}).get("detected_titles") or []
        if metrics["words"] <= 0 and depth_status == "missing":
            detected_label = "—"
        elif detected:
            detected_label = "; ".join(detected[:2])
        else:
            detected_label = "Detectado por contenido"
        row = {
            "role": role,
            "title": label,
            "detected_as": detected_label,
            "words": metrics["words"],
            "citation_count": metrics["citation_count"],
            "citation_density": metrics["citation_density"],
            "critical_markers": metrics["critical_markers"],
            "result_markers": metrics["result_markers"],
            "depth_status": depth_status,
            "depth_label": DEPTH_STATUS_LABELS[depth_status],
            "depth_reason": _depth_reason(role, metrics, depth_status),
        }
        rows.append(row)

    return rows


def _checklist_depth_status(review: dict) -> str | None:
    """Traduce el checklist estructural a un estado de profundidad equivalente."""
    status = review.get("status")
    if status == "fail":
        return "weak"
    if status == "partial":
        return "partial"
    if status == "ok":
        return "adequate"
    return None


def _checklist_depth_reason(review: dict) -> str:
    from savt.chapter_reviews import CHECK_LABELS

    missing = list(review.get("missing") or []) + list(review.get("partial_items") or [])
    if missing:
        labels = [CHECK_LABELS.get(item, item) for item in missing[:3]]
        return f"Checklist: falta o no está claro — {', '.join(labels)}."
    summary = (review.get("summary") or "").strip()
    if summary and summary != "El apartado cumple los criterios detectados automáticamente.":
        return summary
    return ""


def reconcile_section_depth_with_reviews(
    section_depth: list[dict],
    chapter_reviews: list[dict],
) -> list[dict]:
    """
    Alinea profundidad académica con el checklist de presentación.
    Si el checklist marca un apartado como no conforme, la profundidad no puede ser «Conforme».
    """
    reviews_by_key = {review["key"]: review for review in chapter_reviews}
    reconciled: list[dict] = []

    for row in section_depth:
        item = dict(row)
        review_key = CHECKLIST_ALIGNED_ROLES.get(item.get("role", ""))
        if not review_key:
            reconciled.append(item)
            continue

        review = reviews_by_key.get(review_key)
        checklist_status = _checklist_depth_status(review) if review else None
        if not checklist_status:
            reconciled.append(item)
            continue

        metrics_status = item.get("depth_status", "missing")
        if _DEPTH_RANK[checklist_status] < _DEPTH_RANK.get(metrics_status, 3):
            item["depth_status"] = checklist_status
            item["depth_label"] = DEPTH_STATUS_LABELS[checklist_status]
            checklist_reason = _checklist_depth_reason(review)
            if checklist_reason:
                item["depth_reason"] = checklist_reason
            item["aligned_with_checklist"] = True
        else:
            item["aligned_with_checklist"] = metrics_status == checklist_status

        reconciled.append(item)

    return reconciled


def _marco_text(parsed: dict) -> str:
    section_map = parsed.get("section_map") or get_section_map(parsed.get("body", ""))
    marco = section_map.get("marco_teorico", "")
    if len(marco) > 400:
        return marco
    return extract_section(
        parsed.get("body", ""),
        (
            "marco teórico",
            "marco teorico",
            "marco conceptual",
            "revisión de literatura",
            "revision de literatura",
            "antecedentes",
            "estado del arte",
        ),
    )


def audit_content_quality(parsed: dict, config: AuditConfig) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    body = parsed.get("body", "")
    marco = _marco_text(parsed)
    word_stats = build_word_statistics(parsed)
    section_depth = build_section_depth_analysis(parsed)
    marco_row = next((row for row in section_depth if row["role"] == "marco_teorico"), None)
    dashboard: dict = {
        **word_stats,
        "section_depth": section_depth,
        "marco_word_count": marco_row["words"] if marco_row else 0,
        "citation_density_marco": marco_row["citation_density"] if marco_row else 0.0,
        "critical_markers_found": marco_row["critical_markers"] if marco_row else 0,
        "hypothesis_detected": False,
        "results_development": "unknown",
        "indicator_help": {
            "total_body_words": (
                "Palabras del cuerpo del trabajo (sin bibliografía ni anexos finales parseados)."
            ),
            "bibliography_words": "Palabras detectadas en la sección de bibliografía/referencias.",
            "sections": (
                "Total de palabras por apartado canónico. Cada fila corresponde a un tramo "
                "exclusivo del documento (sin doble conteo). La presentación/resumen proviene "
                "del abstract detectado; el resto se delimita por encabezados reales del PDF."
            ),
            "section_depth": (
                "Indicadores de profundidad académica por apartado canónico: extensión, "
                "cantidad de citas bibliográficas detectadas, marcadores de análisis crítico e "
                "indicadores de presentación de hallazgos (en resultados). El estado «Profundidad» "
                "se alinea con el checklist de presentación: si el checklist marca un apartado "
                "como no conforme, aquí tampoco aparecerá como conforme."
            ),
            "marco_word_count": (
                "Palabras en marco teórico / revisión bibliográfica (rol canónico). "
                "Incluido en la tabla por apartados."
            ),
            "citation_density_marco": (
                "Densidad de citas del marco teórico. Ver también la tabla por apartados."
            ),
            "critical_markers_found": (
                "Marcadores críticos en el marco teórico. Ver desglose completo por apartados."
            ),
        },
    }

    if not config.check_content_depth:
        return findings, dashboard

    partition_marco_words = marco_row["words"] if marco_row else 0
    if partition_marco_words > 0:
        critical_found = marco_row["critical_markers"]
        marco_words = partition_marco_words
        density = marco_row["citation_density"]
        dashboard["critical_markers_found"] = critical_found
        dashboard["marco_word_count"] = marco_words
        dashboard["citation_density_marco"] = density

        if marco_words < 800:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Marco teórico breve para el nivel del trabajo",
                    detail=f"Marco teórico detectado: ~{marco_words} palabras.",
                    why="Los jurados suelen valorar profundidad en revisión de literatura.",
                    how_to_fix="Amplíe síntesis crítica de autores clave, debates y vacíos de conocimiento.",
                    section_key="marco_teorico",
                )
            )
        elif critical_found >= 3 or density >= 1.5:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="ok",
                    title="Marco teórico con desarrollo detectable",
                    detail=(
                        f"Extensión ~{marco_words} palabras, densidad de citas {density}/100, "
                        f"marcadores críticos: {critical_found}."
                    ),
                    section_key="marco_teorico",
                )
            )
        else:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Marco teórico descriptivo",
                    detail="El marco podría reforzar contraste, debate o crítica explícita.",
                    how_to_fix="Contraste autores y relacione teorías con su problema de investigación.",
                    section_key="marco_teorico",
                )
            )
    elif marco:
        marco_metrics = _section_metrics(marco)
        critical_found = marco_metrics["critical_markers"]
        marco_words = marco_metrics["words"]
        density = marco_metrics["citation_density"]
        dashboard["critical_markers_found"] = critical_found
        dashboard["marco_word_count"] = marco_words
        dashboard["citation_density_marco"] = density

        if marco_words < 800:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Marco teórico breve para el nivel del trabajo",
                    detail=f"Marco teórico detectado: ~{marco_words} palabras.",
                    why="Los jurados suelen valorar profundidad en revisión de literatura.",
                    how_to_fix="Amplíe síntesis crítica de autores clave, debates y vacíos de conocimiento.",
                    section_key="marco_teorico",
                )
            )
        elif critical_found >= 3 or density >= 1.5:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="ok",
                    title="Marco teórico con desarrollo detectable",
                    detail=(
                        f"Extensión ~{marco_words} palabras, densidad de citas {density}/100, "
                        f"marcadores críticos: {critical_found}."
                    ),
                    section_key="marco_teorico",
                )
            )
        else:
            findings.append(
                Finding(
                    module="Contenido",
                    severity="info",
                    title="Marco teórico descriptivo",
                    detail="El marco podría reforzar contraste, debate o crítica explícita.",
                    how_to_fix="Contraste autores y relacione teorías con su problema de investigación.",
                    section_key="marco_teorico",
                )
            )
    else:
        findings.append(
            Finding(
                module="Contenido",
                severity="warning",
                title="Marco teórico no identificado claramente",
                detail="No se detectó sección de marco teórico, revisión de literatura o antecedentes.",
                why="El marco teórico es dimensión central en evaluaciones académicas.",
                how_to_fix="Incluya capítulo o sección dedicada al marco vinculada al problema.",
            )
        )

    hypothesis_found = any(re.search(p, body, re.IGNORECASE) for p in HYPOTHESIS_PATTERNS)
    dashboard["hypothesis_detected"] = hypothesis_found

    section_map = parsed.get("section_map") or get_section_map(body)
    results_section = section_map.get("resultados", "")
    if not results_section:
        match = re.search(r"(?is)(resultados.+?)(?:discusi[oó]n|conclusiones|bibliograf)", body)
        results_section = match.group(1) if match else ""

    if results_section:
        result_markers = sum(1 for m in RESULTS_MARKERS if m in results_section.lower())
        dashboard["results_development"] = "adequate" if result_markers >= 2 else "weak"

    return findings, dashboard
