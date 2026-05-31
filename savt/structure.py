from __future__ import annotations

import re

from savt.models import Finding


def _find_block(body: str, sections: dict[str, str], keywords: list[str]) -> str:
    numeric_hints = {k for k in keywords if re.match(r"^\d", k)}
    semantic_hints = [k for k in keywords if not re.match(r"^\d", k)]

    best_text = ""
    for key, text in sections.items():
        key_lower = key.lower()
        if numeric_hints and any(h in key_lower for h in numeric_hints):
            if not any(s in key_lower for s in semantic_hints) and semantic_hints:
                continue
        if semantic_hints and any(word in key_lower for word in semantic_hints):
            if len(text) > len(best_text):
                best_text = text
    if len(best_text) > 200:
        return best_text

    for word in semantic_hints:
        pattern = rf"(?is){re.escape(word)}.+?(?:\n(?:CAPÍTULO|CAPITULO|\d+\.\s+[A-Z])|\Z)"
        match = re.search(pattern, body)
        if match and len(match.group(0)) > 200:
            return match.group(0)
    return ""


def _check_items(text: str, items: list[tuple[str, list[str]]]) -> list[dict]:
    lower = text.lower()
    results = []
    for label, hints in items:
        found = any(h in lower for h in hints)
        results.append({"label": label, "ok": found})
    return results


def _merge_intro_checks(checks: list[dict], parsed: dict) -> list[dict]:
    merged = []
    for check in checks:
        label = check["label"]
        ok = check["ok"]
        if label == "pregunta" and parsed.get("research_questions"):
            ok = True
        if label == "objetivos" and parsed.get("objectives"):
            ok = True
        merged.append({**check, "ok": ok})
    return merged


def _build_discussion_checks(discussion: str) -> list[dict]:
    if not discussion or len(discussion) < 80:
        return [
            {"label": "discusion presente", "ok": False},
            {"label": "discusion desarrollo", "ok": False},
            {"label": "interpretación", "ok": False},
            {"label": "confronta literatura", "ok": False},
            {"label": "vincula objetivos", "ok": False},
            {"label": "limitaciones discusion", "ok": False},
            {"label": "implicaciones", "ok": False},
        ]

    content_checks = _check_items(
        discussion,
        [
            (
                "interpretación",
                [
                    "interpret",
                    "significado",
                    "explic",
                    "explica",
                    "comprens",
                    "analiza",
                    "sentido",
                    "sugiere",
                    "evidencia",
                ],
            ),
            (
                "confronta literatura",
                [
                    "literatura",
                    "estudios previos",
                    "investigaciones previas",
                    "trabajos previos",
                    "autores",
                    "concuerda",
                    "coincide",
                    "difiere",
                    "contradice",
                    "similar",
                    "compar",
                    "contrast",
                    "frente a",
                    "respecto a",
                    "en línea con",
                    "en linea con",
                ],
            ),
            (
                "vincula objetivos",
                [
                    "objetivo",
                    "pregunta",
                    "propósito",
                    "proposito",
                    "finalidad",
                    "hallazgo",
                    "meta",
                    "plantead",
                ],
            ),
            (
                "limitaciones discusion",
                ["limitación", "limitacion", "sesgo", "delimit", "debilidad", "restric", "alcance"],
            ),
            (
                "implicaciones",
                [
                    "implic",
                    "recomend",
                    "aporte",
                    "contribuc",
                    "proyecc",
                    "futur",
                    "práctic",
                    "practic",
                    "teóric",
                    "teoric",
                ],
            ),
        ],
    )
    return [
        {"label": "discusion presente", "ok": True},
        {"label": "discusion desarrollo", "ok": len(discussion) > 400},
        *content_checks,
    ]


def audit_structure(parsed: dict) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    body = parsed["body"]
    sections = parsed["sections"]
    conclusions = parsed.get("conclusions", "")

    intro = _find_block(body, sections, ["introduc", "planteamiento", "1.4", "1.5"])
    method = _find_block(body, sections, ["metodolog", "metodo", "materiales y métodos", "material y metodo"])
    marco = _find_block(
        body,
        sections,
        ["marco teórico", "marco teorico", "marco conceptual", "fundament", "estado del arte", "referencial teórico"],
    )
    results = _find_block(body, sections, ["resultado"])
    discussion = _find_block(body, sections, ["discusi"])
    conclusions_block = conclusions or _find_block(body, sections, ["conclus"])

    intro_scope = body[:20000] if parsed.get("research_questions") else (intro or body[:20000])
    method_scope = method or body
    marco_scope = marco or body

    intro_checks = _merge_intro_checks(
        _check_items(
            intro_scope,
            [
                ("problema", ["problema", "problemática", "problematica", "situación problem", "brecha", "planteamiento"]),
                ("justificación", ["justificación", "justificacion", "relevancia", "pertinencia", "importancia"]),
                ("pregunta", ["pregunta de investigación", "pregunta central", "¿"]),
                ("objetivos", ["objetivo general", "objetivos específicos", "objetivos especificos"]),
            ],
        ),
        parsed,
    )
    method_checks = _check_items(
        method_scope,
        [
            ("diseño", ["diseño", "diseno", "enfoque", "tipo de estudio", "metodología", "metodologia", "modelo empírico", "modelo empirico", "materiales y métodos"]),
            ("población", ["población", "poblacion", "universo", "ámbito", "ambito", "contexto"]),
            ("muestra", ["muestra", "casos", "participantes", "dataset", "datos", "microdatos", "eph", "encuesta"]),
            ("variables", ["variable", "indicador", "dimensión", "dimension"]),
            ("limitaciones", ["limitación", "limitacion", "delimitación", "delimitacion", "alcance"]),
        ],
    )
    marco_checks = _check_items(
        marco_scope,
        [
            ("marco presente", ["marco teórico", "marco teorico", "marco conceptual", "fundamentación teórica", "marco referencial"]),
            ("marco desarrollado", ["autor", "autores", "concepto", "teoría", "teoria", "paradigma", "enfoque teórico"]),
            ("marco vinculado", ["pregunta", "objetivo", "problema", "investigación", "investigacion", "hipótesis", "hipotesis"]),
        ],
    )
    if marco and len(marco) > 400:
        marco_checks = [{**c, "ok": c["ok"] or True} if c["label"] == "marco presente" else c for c in marco_checks]

    results_checks = [
        {"label": "resultados presente", "ok": bool(results)},
        {"label": "resultados desarrollo", "ok": len(results) > 400},
    ]
    discussion_checks = _build_discussion_checks(discussion)

    question_ok = any(c["ok"] for c in intro_checks if c["label"] == "pregunta") or bool(
        parsed.get("research_questions")
    )
    objectives_ok = any(c["ok"] for c in intro_checks if c["label"] == "objetivos") or bool(
        parsed.get("objectives")
    )
    conclusions_objectives = objectives_ok and len(conclusions_block) > 300
    explicit_answer = "en respuesta a la pregunta" in conclusions_block.lower()
    question_keywords = parsed.get("research_questions", [""])[0].lower() if parsed.get("research_questions") else ""
    question_tokens = re.findall(r"[a-záéíóúñ]{5,}", question_keywords)[:6]
    answered_tokens = sum(1 for t in question_tokens if t in conclusions_block.lower())
    conclusions_question = explicit_answer or answered_tokens >= max(2, len(question_tokens) // 2)

    conclusion_checks = [
        {"label": "responde objetivos", "ok": conclusions_objectives},
        {
            "label": "responde la pregunta",
            "ok": conclusions_question,
            "partial": conclusions_objectives and not conclusions_question,
        },
    ]

    dashboard = {
        "introduccion": {"checks": intro_checks, "present": bool(intro or intro_scope)},
        "marco_teorico": {"checks": marco_checks, "present": bool(marco and len(marco) > 300)},
        "metodologia": {"checks": method_checks, "present": bool(method)},
        "resultados": {"checks": results_checks, "present": bool(results), "length": len(results)},
        "discusion": {"checks": discussion_checks, "present": bool(discussion), "length": len(discussion)},
        "conclusiones": {"checks": conclusion_checks, "present": bool(conclusions_block)},
    }

    intro_missing = [c["label"] for c in intro_checks if not c["ok"]]
    core_intro = {"problema", "justificación", "pregunta", "objetivos"}
    intro_core_missing = [c for c in intro_missing if c in core_intro]
    if intro_core_missing:
        findings.append(
            Finding(
                module="Estructura",
                severity="warning" if len(intro_core_missing) > 2 else "info",
                area="Estructura",
                title="Introducción incompleta",
                detail=f"Elementos no detectados claramente: {', '.join(intro_core_missing)}.",
                why="La introducción debe encuadrar problema, relevancia, pregunta y objetivos.",
                how_to_fix="Complete las secciones faltantes con subtítulos explícitos en la introducción.",
            )
        )
    else:
        findings.append(
            Finding(
                module="Estructura",
                severity="ok",
                area="Estructura",
                title="Introducción estructuralmente completa",
                detail="Se detectaron problema, justificación, pregunta y objetivos.",
            )
        )

    method_missing = [c["label"] for c in method_checks if not c["ok"]]
    method_core_missing = [c for c in method_missing if c in {"diseño", "muestra", "variables"}]
    if method_core_missing:
        from savt.chapter_reviews import CHECK_LABELS

        missing_names = ", ".join(CHECK_LABELS.get(m, m) for m in method_core_missing)
        findings.append(
            Finding(
                module="Metodología",
                severity="warning" if "diseño" in method_core_missing else "info",
                area="Metodología",
                title="Metodología con elementos faltantes",
                detail=f"No detectados claramente: {missing_names}.",
                why="La metodología debe permitir evaluar validez y reproducibilidad del estudio.",
                how_to_fix="Agregue subsecciones explícitas para diseño, población/muestra, variables y limitaciones.",
            )
        )
    else:
        findings.append(
            Finding(
                module="Metodología",
                severity="ok",
                area="Metodología",
                title="Metodología con componentes principales",
                detail="Diseño, población, muestra, variables y limitaciones detectados.",
            )
        )

    marco_missing = [c["label"] for c in marco_checks if not c["ok"]]
    if marco_missing and not dashboard["marco_teorico"]["present"]:
        findings.append(
            Finding(
                module="Estructura",
                severity="warning",
                area="Estructura",
                title="Marco teórico no detectado o insuficiente",
                detail="No se identificó un marco teórico desarrollado con claridad.",
                why="El marco teórico sustenta conceptos, autores y debates del estudio.",
                how_to_fix="Incluya un capítulo de marco teórico vinculado a su pregunta de investigación.",
            )
        )
    elif marco_missing:
        findings.append(
            Finding(
                module="Estructura",
                severity="info",
                area="Estructura",
                title="Marco teórico mejorable",
                detail=f"Aspectos a reforzar: {', '.join(marco_missing)}.",
                why="Un marco bien articulado conecta teoría, pregunta y resultados.",
                how_to_fix="Profundice autores clave y cierre el marco hacia su problema de investigación.",
            )
        )

    for section_name, present, label in [
        ("Resultados", results, "Sección de resultados"),
        ("Discusión", discussion, "Sección de discusión"),
    ]:
        if present:
            findings.append(
                Finding(
                    module="Estructura",
                    severity="ok",
                    area="Estructura",
                    title=f"{label} presente",
                    detail=f"Se identificó desarrollo de {section_name.lower()}.",
                )
            )
        else:
            from savt.chapter_reviews import CHECK_GUIDANCE

            disc_guide = CHECK_GUIDANCE["discusion presente"]
            why = disc_guide["why"] if section_name == "Discusión" else (
                "Es un capítulo obligatorio en la estructura académica estándar."
            )
            how = disc_guide["how_to_fix"] if section_name == "Discusión" else (
                f"Incluya un capítulo o sección titulada '{section_name}' con subtítulos numerados."
            )
            findings.append(
                Finding(
                    module="Estructura",
                    severity="warning",
                    area="Estructura",
                    title=f"{label} no detectada",
                    detail=f"No se encontró una sección clara de {section_name.lower()}.",
                    why=why,
                    how_to_fix=how,
                )
            )

    if not conclusions_question:
        findings.append(
            Finding(
                module="Conclusiones",
                severity="warning",
                area="Conclusiones",
                title="Conclusiones no responden explícitamente la pregunta",
                detail="Las conclusiones no reformulan ni responden de forma directa la pregunta de investigación.",
                why="El evaluador verifica que el trabajo haya respondido lo que prometió investigar.",
                how_to_fix="Inicie las conclusiones con un párrafo que responda la pregunta usando sus hallazgos.",
            )
        )

    return findings, dashboard
