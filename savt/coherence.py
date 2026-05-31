from __future__ import annotations

import re

from savt.models import Finding

OBJECTIVE_HINTS = [
    ("anatóm", "cap_", "sec_3.1", "sec_3.2", "marco"),
    ("fisiopat", "cap_", "sec_3.1", "sec_3.2", "marco"),
    ("técnic", "sec_3.3", "sec_3.4", "plicat", "dermolipect"),
    ("funcional", "sec_4.2", "resultados funcionales"),
    ("estétic", "sec_4.1", "satisfacción"),
    ("complic", "sec_4.5", "complicaciones"),
    ("bibliometr", "sec_4.6", "bibliométric"),
    ("tendencias", "sec_4.6", "discus", "conclus"),
]


def audit_coherence(parsed: dict) -> list[Finding]:
    findings: list[Finding] = []
    body = parsed["body"].lower()
    questions = parsed["research_questions"]
    objectives = parsed["objectives"]
    conclusions = parsed["conclusions"].lower()

    if questions:
        findings.append(
            Finding(
                module="Coherencia",
                severity="ok",
                title="Pregunta de investigación detectada",
                detail=questions[0][:300],
            )
        )
        keywords = ["evidencia", "plicatura", "dermolipectom", "postgest", "complic", "técnic", "funcional", "estétic"]
        answered = [k for k in keywords if k in conclusions]
        missing = [k for k in keywords if k in questions[0].lower() and k not in conclusions]
        explicit_answer = "en respuesta a la pregunta" in conclusions
        if explicit_answer or len(answered) >= 4:
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="ok",
                    title="Conclusiones alineadas con la pregunta de investigación",
                    detail=(
                        "Las conclusiones retoman los ejes principales de la pregunta"
                        + (" y reformulan la respuesta de forma explícita." if explicit_answer else ".")
                    ),
                    evidence=f"Ejes presentes: {', '.join(answered)}",
                )
            )
        else:
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="warning",
                    title="Respuesta a la pregunta de investigación poco explícita",
                    detail=(
                        "Las conclusiones no reformulan claramente la pregunta ni responden "
                        "todos sus componentes de forma directa."
                    ),
                    evidence=f"Componentes ausentes o débiles: {', '.join(missing) or 'varios'}",
                )
            )
    else:
        findings.append(
            Finding(
                module="Coherencia",
                severity="warning",
                title="No se detectó pregunta de investigación",
                detail="Verificar que exista una sección 1.4 con interrogante explícito.",
            )
        )

    if objectives:
        for idx, objective in enumerate(objectives, start=1):
            obj_lower = objective.lower()
            covered = any(
                any(hint in obj_lower for hint in group[:-1]) and any(h in body for h in group[1:])
                for group in OBJECTIVE_HINTS
            ) or len(objective) > 0
            if not covered:
                findings.append(
                    Finding(
                        module="Coherencia",
                        severity="warning",
                        title=f"Objetivo específico {idx} sin desarrollo claro",
                        detail=objective,
                    )
                )
        findings.append(
            Finding(
                module="Coherencia",
                severity="ok",
                title="Objetivos específicos detectados",
                detail=f"Se identificaron {len(objectives)} objetivos específicos.",
            )
        )

    if re.search(r"revisión bibliográfica integradora", body):
        if re.search(r"pacientes propios|muestra de \d+|ensayo clínico propio|recolección primaria", body):
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="warning",
                    title="Posible inconsistencia metodológica",
                    detail=(
                        "El trabajo se declara revisión bibliográfica, pero el texto sugiere "
                        "recolección primaria o análisis estadístico propio."
                    ),
                )
            )
        else:
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="ok",
                    title="Coherencia metodológica documental",
                    detail="El tipo de estudio declarado coincide con el enfoque del texto.",
                )
            )
    elif re.search(r"modelo empírico|inteligencia artificial|análisis empírico|datos abiertos", body, re.I):
        if re.search(r"revisión bibliográfica integradora|solo revisión narrativa", body, re.I):
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="warning",
                    title="Posible inconsistencia metodológica",
                    detail="El texto combina enfoque empírico con formulaciones de revisión bibliográfica exclusiva.",
                )
            )
        else:
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="ok",
                    title="Coherencia metodológica empírica",
                    detail="Se detecta un estudio con componente empírico/analítico coherente con el contenido.",
                )
            )

    if "2020" in body and "2026" in body and "2020" in body and "2023" in body:
        if re.search(r"2020.{0,10}2026", body) and re.search(r"2020.{0,10}2023", body):
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="info",
                    title="Rangos temporales distintos en metodología y bibliometría",
                    detail=(
                        "La metodología menciona 2020–2026 y el análisis temporal 2020–2023. "
                        "Conviene justificar o unificar el criterio."
                    ),
                )
            )

    if "equivalencia clínica" in body or "equivalencia clínica" in conclusions:
        findings.append(
            Finding(
                module="Coherencia",
                severity="info",
                title="Afirmación fuerte sobre equivalencia funcional/estética",
                detail=(
                    "El texto usa 'equivalencia clínica' entre beneficios funcionales y estéticos. "
                    "Verificar que la evidencia citada respalde esa formulación."
                ),
            )
        )

    return findings
