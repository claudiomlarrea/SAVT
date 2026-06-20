from __future__ import annotations

from savt.models import AuditReport, Finding


def _questions_from_findings(report: AuditReport, max_q: int = 8) -> list[dict]:
    questions: list[dict] = []
    category_map = {
        "Metodología": "Metodología",
        "Coherencia": "Coherencia argumental",
        "Bibliografía": "Bibliografía",
        "Citas": "Bibliografía",
        "Estructura": "Estructura",
        "Conclusiones": "Conclusiones",
        "Redacción": "Redacción",
        "Integridad": "Integridad académica",
        "Ética": "Ética de investigación",
        "Originalidad": "Aporte y originalidad",
        "Normativa": "Aspectos formales",
        "Contenido": "Marco teórico y profundidad",
    }

    for finding in report.findings:
        if finding.severity not in ("error", "warning"):
            continue
        area = finding.area or finding.module
        category = category_map.get(area, area)
        question = _finding_to_question(finding)
        if question and not any(q["question"] == question for q in questions):
            questions.append(
                {
                    "category": category,
                    "question": question,
                    "based_on": finding.title,
                }
            )
        if len(questions) >= max_q:
            break
    return questions


def _finding_to_question(finding: Finding) -> str:
    title = finding.title.lower()
    if "marco teórico" in title:
        return "¿Cómo se relaciona su marco teórico con la pregunta de investigación y los objetivos?"
    if "metodolog" in title:
        return "¿Por qué eligió este diseño metodológico y cómo garantiza validez de sus resultados?"
    if "conclus" in title or "pregunta" in title:
        return "¿En qué medida sus conclusiones responden a la pregunta y objetivos planteados?"
    if "bibliograf" in title or "cita" in title:
        return "¿Cómo verificó la correspondencia entre citas en el texto y referencias bibliográficas?"
    if "ética" in title or "etica" in title:
        return "¿Qué consideraciones éticas aplicó y cómo fueron aprobadas institucionalmente?"
    if "similitud" in title or "integridad" in title:
        return "¿Cómo garantizó la originalidad del texto y el uso adecuado de fuentes?"
    if "originalidad" in title or "aporte" in title:
        return "¿Cuál es el aporte principal de su trabajo al campo de estudio?"
    if "hipótesis" in title or "hipotesis" in title:
        return "¿Cuáles fueron sus hipótesis y cómo fueron contrastadas con los datos?"
    if "figura" in title or "tabla" in title:
        return "¿Cómo integra las figuras y tablas al argumento central de su tesis?"
    if "extensión" in title or "extension" in title:
        return "¿Considera que la extensión del trabajo es adecuada para el nivel de profundidad alcanzado?"
    return f"¿Cómo respondería a la observación: «{finding.title}»?"


def _standard_questions(parsed: dict) -> list[dict]:
    base = [
        {
            "category": "General",
            "question": "¿Cuál es el problema de investigación y por qué es relevante en su disciplina?",
            "based_on": "Estándar de defensa oral",
        },
        {
            "category": "Metodología",
            "question": "¿Qué limitaciones tuvo su diseño y cómo las mitigó?",
            "based_on": "Estándar de defensa oral",
        },
        {
            "category": "Aporte",
            "question": "¿Qué aporta su trabajo que no estaba suficientemente cubierto en la literatura?",
            "based_on": "Estándar de defensa oral",
        },
        {
            "category": "Futuro",
            "question": "¿Qué líneas de investigación futura se abren a partir de sus hallazgos?",
            "based_on": "Estándar de defensa oral",
        },
    ]
    if parsed.get("objectives"):
        base.insert(
            1,
            {
                "category": "Objetivos",
                "question": "Repase cada objetivo específico: ¿fue alcanzado? ¿con qué evidencia?",
                "based_on": "Objetivos detectados",
            },
        )
    if parsed.get("research_questions"):
        base.insert(
            0,
            {
                "category": "Pregunta",
                "question": f"¿Cómo responde su trabajo a: «{parsed['research_questions'][0][:120]}»?",
                "based_on": "Pregunta de investigación",
            },
        )
    return base


def build_defense_prep(
    report: AuditReport,
    parsed: dict,
    extras: dict | None = None,
) -> dict:
    extras = extras or {}
    from_findings = _questions_from_findings(report, max_q=6)
    standard = _standard_questions(parsed)

    seen: set[str] = set()
    combined: list[dict] = []
    for item in from_findings + standard:
        if item["question"] in seen:
            continue
        seen.add(item["question"])
        combined.append(item)

    ethics = extras.get("ethics_dashboard") or {}
    if ethics.get("is_empirical") and not any(
        q["category"] == "Ética de investigación" for q in combined
    ):
        combined.append(
            {
                "category": "Ética de investigación",
                "question": "¿Cómo obtuvo el consentimiento de los participantes y protegió sus datos?",
                "based_on": "Investigación empírica detectada",
            }
        )

    tips = [
        "Prepare una síntesis oral de 3–5 minutos: problema, método, hallazgos y aporte.",
        "Tenga a mano las figuras/tablas clave para explicar resultados.",
        "Anticipe preguntas sobre limitaciones y cómo las abordó.",
        "Revise correspondencia citas–bibliografía antes de la defensa.",
    ]

    return {
        "questions": combined[:12],
        "tips": tips,
        "total": len(combined[:12]),
    }
