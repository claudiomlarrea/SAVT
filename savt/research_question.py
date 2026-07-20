from __future__ import annotations

import re

from savt.models import Finding


def audit_research_question(parsed: dict) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    body = parsed["body"]
    questions = parsed.get("research_questions") or []
    conclusions = (parsed.get("conclusions") or "").lower()
    thesis_type = parsed.get("thesis_type") or "clasica"
    section_map = parsed.get("section_map") or {}
    objectives_block = (section_map.get("objetivos") or parsed.get("objectives") or "").strip()

    if thesis_type == "compendio" and not questions:
        has_objectives = bool(
            re.search(r"objetivo\s+general", objectives_block or body, re.IGNORECASE)
        ) or bool(parsed.get("objectives"))
        if has_objectives:
            checks = [
                {"label": "Claramente formulada", "ok": False, "partial": True},
                {"label": "Aparece en introducción", "ok": False, "partial": True},
                {
                    "label": "Se responde explícitamente en conclusiones",
                    "ok": False,
                    "partial": True,
                },
            ]
            findings.append(
                Finding(
                    module="Pregunta de investigación",
                    severity="info",
                    area="Coherencia",
                    title="Compendio: objetivos en lugar de pregunta única",
                    detail=(
                        "En tesis por artículos/capítulos el foco suele declararse con objetivos "
                        "(p. ej. Cap. III) en lugar de una pregunta monográfica en la introducción."
                    ),
                    why="No implica incoherencia si los objetivos guían cada artículo.",
                    how_to_fix=(
                        "Opcional: formule una pregunta integradora en el capítulo de planteamiento "
                        "o vincule explícitamente cada objetivo con los artículos empíricos."
                    ),
                )
            )
            return findings, {"question": "", "checks": checks}

    if not questions:
        findings.append(
            Finding(
                module="Pregunta de investigación",
                severity="warning",
                area="Coherencia",
                title="Pregunta de investigación no detectada",
                detail="No se encontró un interrogante explícito en la introducción.",
                why="La pregunta define el foco evaluable del trabajo.",
                how_to_fix=(
                    "Formule la pregunta en una sección dedicada (p. ej. «Pregunta de investigación»), "
                    "o declare el «Tema de la tesis» / problema de investigación con un interrogante explícito."
                ),
            )
        )
        return findings, {"question": "", "checks": []}

    question = questions[0]
    well_formed = len(question) > 30 and question.strip().endswith("?")
    in_intro = bool(
        re.search(
            r"(?is)(?:pregunta de investigación|pregunta central).{0,400}"
            + re.escape(question[:40]),
            body,
        )
    ) or "pregunta de investigación" in body.lower()

    explicit_answer = "en respuesta a la pregunta" in conclusions
    tokens = re.findall(r"[a-záéíóúñ]{5,}", question.lower())[:8]
    token_hits = sum(1 for t in tokens if t in conclusions)
    answered = explicit_answer or token_hits >= max(2, len(tokens) // 2)

    checks = [
        {"label": "Claramente formulada", "ok": well_formed},
        {"label": "Aparece en introducción", "ok": in_intro},
        {
            "label": "Se responde explícitamente en conclusiones",
            "ok": answered,
            "partial": not answered and token_hits >= 1,
        },
    ]

    if well_formed:
        findings.append(
            Finding(
                module="Pregunta de investigación",
                severity="ok",
                area="Coherencia",
                title="Pregunta claramente formulada",
                detail=question[:350],
            )
        )
    else:
        findings.append(
            Finding(
                module="Pregunta de investigación",
                severity="warning",
                area="Coherencia",
                title="Pregunta poco clara o muy breve",
                detail=question[:350],
                how_to_fix="Redacte una pregunta completa, específica y terminada en signo de interrogación.",
            )
        )

    if in_intro:
        findings.append(
            Finding(
                module="Pregunta de investigación",
                severity="ok",
                area="Coherencia",
                title="Pregunta ubicada en introducción",
                detail="La pregunta aparece en el marco introductorio del trabajo.",
            )
        )

    if answered:
        findings.append(
            Finding(
                module="Pregunta de investigación",
                severity="ok",
                area="Coherencia",
                title="Pregunta respondida en conclusiones",
                detail="Las conclusiones retoman elementos centrales de la pregunta.",
            )
        )
    else:
        findings.append(
            Finding(
                module="Pregunta de investigación",
                severity="warning",
                area="Coherencia",
                title="Pregunta no respondida explícitamente en conclusiones",
                detail="Las conclusiones no cierran el ciclo con una respuesta directa.",
                why="Es uno de los criterios más observados por evaluadores y jurados.",
                how_to_fix="Agregue un párrafo de cierre que responda la pregunta con sus principales hallazgos.",
            )
        )

    return findings, {"question": question, "checks": checks}
