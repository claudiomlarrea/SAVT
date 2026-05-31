from __future__ import annotations

CHECK_LABELS: dict[str, str] = {
    "problema": "Planteamiento del problema",
    "justificación": "Justificación / relevancia",
    "pregunta": "Pregunta de investigación",
    "objetivos": "Objetivos general y específicos",
    "diseño": "Diseño y tipo de estudio",
    "población": "Población / universo / contexto",
    "muestra": "Muestra / datos / participantes",
    "variables": "Variables o indicadores",
    "limitaciones": "Limitaciones o delimitaciones",
    "marco presente": "Marco teórico identificado",
    "marco desarrollado": "Desarrollo teórico suficiente",
    "marco vinculado": "Vinculación con la pregunta de investigación",
    "presente": "Sección identificada con desarrollo suficiente",
    "resultados presente": "Capítulo o sección de resultados identificada",
    "resultados desarrollo": "Desarrollo suficiente de resultados",
    "discusion presente": "Capítulo o sección de discusión identificada",
    "discusion desarrollo": "Desarrollo analítico suficiente en la discusión",
    "interpretación": "Interpretación de los hallazgos",
    "confronta literatura": "Confrontación con marco teórico y literatura",
    "vincula objetivos": "Vinculación con pregunta y objetivos",
    "limitaciones discusion": "Reconocimiento de limitaciones en la discusión",
    "implicaciones": "Implicaciones, aportes o líneas futuras",
    "responde objetivos": "Respuesta a los objetivos",
    "responde la pregunta": "Respuesta explícita a la pregunta",
}

CHECK_GUIDANCE: dict[str, dict[str, str]] = {
    "problema": {
        "why": "Sin problema no queda claro qué investiga ni por qué importa el trabajo.",
        "how_to_fix": "Redacte un apartado que describa la situación problemática, la brecha o necesidad de estudio.",
    },
    "justificación": {
        "why": "La justificación explica la relevancia académica, social o institucional del estudio.",
        "how_to_fix": "Agregue un subtítulo de justificación con argumentos de pertinencia y aporte esperado.",
    },
    "pregunta": {
        "why": "La pregunta orienta objetivos, metodología y conclusiones.",
        "how_to_fix": "Formule una pregunta explícita en la introducción, idealmente en sección dedicada (p. ej. 1.4).",
    },
    "objetivos": {
        "why": "Los objetivos definen qué debe quedar resuelto al final del trabajo.",
        "how_to_fix": "Liste objetivo general y objetivos específicos numerados, medibles y alineados con la pregunta.",
    },
    "diseño": {
        "why": "El diseño permite evaluar si el método responde a la pregunta planteada.",
        "how_to_fix": "Indique si el estudio es documental, empírico, mixto, bibliométrico, etc., y describa el enfoque.",
    },
    "población": {
        "why": "Delimitar población o contexto evita ambigüedad sobre el alcance del estudio.",
        "how_to_fix": "Describa universo, ámbito geográfico, institucional o temporal del estudio.",
    },
    "muestra": {
        "why": "La muestra o fuente de datos debe ser identificable para evaluar validez.",
        "how_to_fix": "Especifique casos, participantes, bases de datos, encuestas o corpus utilizados.",
    },
    "variables": {
        "why": "Las variables o indicadores conectan la teoría con los resultados.",
        "how_to_fix": "Nombre y describa las variables, dimensiones o indicadores analizados.",
    },
    "limitaciones": {
        "why": "Declarar limitaciones demuestra rigor y transparencia metodológica.",
        "how_to_fix": "Incluya un apartado breve sobre alcance, sesgos o restricciones del estudio.",
    },
    "marco presente": {
        "why": "El marco teórico sustenta conceptualmente la investigación.",
        "how_to_fix": "Agregue un capítulo o sección titulada 'Marco teórico' o 'Marco conceptual'.",
    },
    "marco desarrollado": {
        "why": "Un marco breve o ausente debilita el fundamento del análisis.",
        "how_to_fix": "Desarrolle autores, conceptos y debates centrales vinculados al tema.",
    },
    "marco vinculado": {
        "why": "El marco debe converger hacia su pregunta y objetivos, no ser un catálogo aislado.",
        "how_to_fix": "Cierre el marco teórico relacionando conceptos clave con su problema de investigación.",
    },
    "presente": {
        "why": "Es un capítulo obligatorio en la estructura académica estándar.",
        "how_to_fix": "Incluya un capítulo claramente titulado con subtítulos numerados y desarrollo analítico.",
    },
    "resultados presente": {
        "why": "Los resultados presentan de forma ordenada los hallazgos obtenidos.",
        "how_to_fix": "Agregue un capítulo de resultados con subtítulos alineados a sus objetivos específicos.",
    },
    "resultados desarrollo": {
        "why": "Los hallazgos deben describirse con suficiente detalle para ser evaluados.",
        "how_to_fix": "Amplíe tablas, figuras y narrativa descriptiva de los resultados obtenidos.",
    },
    "discusion presente": {
        "why": (
            "Según Hernández, Fernández y Baptista, la discusión cumple una función distinta a los "
            "resultados: interpretar los hallazgos, confrontarlos con la literatura y argumentar su "
            "significado frente a la pregunta de investigación."
        ),
        "how_to_fix": (
            "Incluya un capítulo titulado «Discusión», separado de Resultados y Conclusiones, "
            "con subtítulos numerados."
        ),
    },
    "discusion desarrollo": {
        "why": (
            "Una discusión breve o superficial suele limitarse a repetir resultados sin analizar "
            "similitudes, diferencias ni causas posibles respecto de estudios previos."
        ),
        "how_to_fix": (
            "Desarrolle párrafos analíticos que interpreten cada hallazgo relevante y lo compare "
            "con autores citados en su marco teórico."
        ),
    },
    "interpretación": {
        "why": (
            "La discusión debe explicar el significado de los resultados —no solo reportarlos— "
            "indicando qué aportan al problema estudiado."
        ),
        "how_to_fix": (
            "Redacte párrafos que respondan «¿qué significa este hallazgo?» y «¿cómo se relaciona "
            "con la pregunta de investigación?»."
        ),
    },
    "confronta literatura": {
        "why": (
            "Un evaluador académico espera que los resultados se contrasten con investigaciones "
            "previas: coincidencias, divergencias y posibles explicaciones."
        ),
        "how_to_fix": (
            "Cite autores del marco teórico y compare explícitamente sus postulados o hallazgos "
            "con los suyos (concuerda, difiere, amplía, contradice)."
        ),
    },
    "vincula objetivos": {
        "why": (
            "La discusión debe cerrar el ciclo metodológico retomando la pregunta y los objetivos "
            "planteados al inicio del trabajo."
        ),
        "how_to_fix": (
            "Retome la pregunta de investigación y cada objetivo específico al interpretar los "
            "resultados obtenidos."
        ),
    },
    "limitaciones discusion": {
        "why": (
            "Reconocer limitaciones del diseño, la muestra o el análisis demuestra rigor y evita "
            "sobreinterpretaciones."
        ),
        "how_to_fix": (
            "Incluya un apartado breve sobre restricciones metodológicas y cómo afectan la "
            "generalización de los hallazgos."
        ),
    },
    "implicaciones": {
        "why": (
            "Las implicaciones teóricas, prácticas o institucionales muestran el aporte del estudio "
            "más allá del informe de datos."
        ),
        "how_to_fix": (
            "Cierre la discusión con aportes al campo, recomendaciones aplicables y posibles "
            "investigaciones futuras."
        ),
    },
    "responde objetivos": {
        "why": "Las conclusiones deben demostrar que se cumplieron los objetivos planteados.",
        "how_to_fix": "Retome cada objetivo específico y sintetice cómo fue respondido.",
    },
    "responde la pregunta": {
        "why": "El evaluador verifica que el trabajo respondió lo que prometió investigar.",
        "how_to_fix": "Inicie las conclusiones con un párrafo que responda la pregunta con los hallazgos.",
    },
}

SECTION_TITLES: dict[str, str] = {
    "introduccion": "Introducción",
    "objetivos": "Objetivos",
    "marco_teorico": "Marco teórico",
    "metodologia": "Metodología / Materiales y métodos",
    "resultados": "Resultados",
    "discusion": "Discusión",
    "conclusiones": "Conclusiones",
    "bibliografia": "Bibliografía",
}


def _missing_guidance(missing_labels: list[str]) -> tuple[str, str, str]:
    if not missing_labels:
        return "", "", ""
    whys = []
    fixes = []
    for label in missing_labels:
        guide = CHECK_GUIDANCE.get(label, {})
        if guide.get("why"):
            whys.append(f"**{CHECK_LABELS.get(label, label)}:** {guide['why']}")
        if guide.get("how_to_fix"):
            fixes.append(f"**{CHECK_LABELS.get(label, label)}:** {guide['how_to_fix']}")
    summary = "Faltan o no están claros: " + ", ".join(CHECK_LABELS.get(l, l) for l in missing_labels) + "."
    return summary, "\n".join(whys), "\n".join(fixes)


def _review_from_checks(section_key: str, block: dict, required: set[str] | None = None) -> dict:
    checks = block.get("checks", [])
    present = block.get("present", False)
    if required is None:
        required = {c["label"] for c in checks}

    missing = [
        c["label"]
        for c in checks
        if c["label"] in required and not c.get("ok") and not c.get("partial")
    ]
    partial = [c["label"] for c in checks if c.get("partial")]

    if not present and not checks:
        missing = ["presente"]

    if not missing and not partial and (present or all(c.get("ok") for c in checks if c["label"] in required)):
        status = "ok"
    elif missing:
        status = "fail"
    elif partial:
        status = "partial"
    else:
        status = "ok"

    summary, why, how_to_fix = _missing_guidance(missing + partial)

    if status == "ok":
        summary = "El apartado cumple los criterios detectados automáticamente."
        why = "La estructura y el contenido mínimo esperado están presentes."
        how_to_fix = ""

    return {
        "key": section_key,
        "title": SECTION_TITLES.get(section_key, section_key),
        "status": status,
        "ok": status == "ok",
        "partial": status == "partial",
        "missing": missing,
        "partial_items": partial,
        "summary": summary,
        "why": why,
        "how_to_fix": how_to_fix,
        "checks": checks,
    }


def build_discussion_review(block: dict) -> dict:
    checks = block.get("checks", [])
    present = block.get("present", False)
    text_length = block.get("length", 0)

    core_required = {
        "discusion presente",
        "discusion desarrollo",
        "interpretación",
        "confronta literatura",
        "vincula objetivos",
    }
    optional = {"limitaciones discusion", "implicaciones"}

    missing = [
        c["label"]
        for c in checks
        if c["label"] in core_required and not c.get("ok") and not c.get("partial")
    ]
    partial = [
        c["label"]
        for c in checks
        if c.get("partial") or (c["label"] in optional and not c.get("ok"))
    ]

    if not present and "discusion presente" not in missing:
        missing.insert(0, "discusion presente")

    if not missing and not partial:
        return {
            "key": "discusion",
            "title": SECTION_TITLES["discusion"],
            "status": "ok",
            "ok": True,
            "partial": False,
            "missing": [],
            "partial_items": [],
            "summary": (
                "La discusión interpreta los hallazgos, los confronta con la literatura "
                "y los vincula con la pregunta y los objetivos del estudio."
            ),
            "why": (
                "El apartado cumple la función académica de la discusión según la metodología "
                "de investigación: interpretar, contrastar y argumentar —no solo repetir resultados."
            ),
            "how_to_fix": "",
            "checks": checks,
        }

    summary_parts: list[str] = []
    if "discusion presente" in missing:
        summary_parts.append("no se identificó un capítulo o sección autónoma de Discusión")
    elif "discusion desarrollo" in missing:
        words_est = max(1, text_length // 5)
        summary_parts.append(
            f"la sección detectada es insuficiente (aprox. {words_est} palabras; se espera desarrollo analítico amplio)"
        )
    else:
        missing_names = [CHECK_LABELS.get(label, label) for label in missing]
        if missing_names:
            summary_parts.append("no se evidencia claramente: " + "; ".join(missing_names))
    if partial:
        partial_names = [CHECK_LABELS.get(label, label) for label in partial if label not in missing]
        if partial_names:
            summary_parts.append("convendría reforzar: " + "; ".join(partial_names))

    summary = "Requiere revisión: " + ". ".join(summary_parts) + "."

    why_parts: list[str] = []
    if "discusion presente" in missing:
        why_parts.append(CHECK_GUIDANCE["discusion presente"]["why"])
        why_parts.append(
            "Sin discusión, el evaluador no puede verificar si el tesista comprende sus propios "
            "hallazgos ni si dialoga con el estado del arte planteado en el marco teórico."
        )
    else:
        why_parts.append(
            "En la estructura del reporte de investigación, la discusión es el espacio de "
            "argumentación académica: interpreta resultados, los contrasta con autores previos "
            "y explica su relevancia para la pregunta planteada."
        )
        for label in missing + partial:
            guide = CHECK_GUIDANCE.get(label, {})
            if guide.get("why") and label not in {"discusion presente"}:
                why_parts.append(guide["why"])

    how_parts: list[str] = []
    if "discusion presente" in missing:
        how_parts.append(CHECK_GUIDANCE["discusion presente"]["how_to_fix"])
    how_parts.append(
        "Estructure la discusión en párrafos que: (1) interpreten cada hallazgo; "
        "(2) lo comparen con la literatura citada; (3) retomen la pregunta y los objetivos; "
        "(4) reconozcan limitaciones; (5) señalen implicaciones o aportes del estudio."
    )
    for label in missing + partial:
        guide = CHECK_GUIDANCE.get(label, {})
        if guide.get("how_to_fix") and label != "discusion presente":
            how_parts.append(guide["how_to_fix"])

    status = "fail" if missing else "partial"

    return {
        "key": "discusion",
        "title": SECTION_TITLES["discusion"],
        "status": status,
        "ok": False,
        "partial": status == "partial",
        "missing": missing,
        "partial_items": [p for p in partial if p not in missing],
        "summary": summary,
        "why": " ".join(dict.fromkeys(why_parts)),
        "how_to_fix": " ".join(dict.fromkeys(how_parts)),
        "checks": checks,
    }


def build_bibliography_review(bib_dashboard: dict, warnings_list: list[dict]) -> dict:
    details = bib_dashboard.get("details") or {}
    unmatched = bib_dashboard.get("unmatched_citations", 0)
    out_period = bib_dashboard.get("out_of_period", 0)
    off_topic = bib_dashboard.get("possibly_off_topic", 0)
    coverage = bib_dashboard.get("coverage", "adecuada")

    issues: list[str] = []
    if unmatched:
        issues.append(f"{unmatched} citas no emparejadas con la bibliografía")
    if out_period:
        issues.append(f"{out_period} referencias anteriores al período metodológico")
    if off_topic:
        issues.append(f"{off_topic} referencias posiblemente ajenas al tema")
    if coverage == "requiere revisión":
        issues.append("cobertura bibliográfica insuficiente")

    doi_warnings = [w for w in warnings_list if "DOI" in w.get("finding_title_raw", "")]
    if doi_warnings:
        issues.append("problemas con DOI o URLs bibliográficas")

    if not issues:
        return {
            "key": "bibliografia",
            "title": SECTION_TITLES["bibliografia"],
            "status": "ok",
            "ok": True,
            "partial": False,
            "summary": "Bibliografía consistente con las citas detectadas en el texto.",
            "why": "Las referencias están alineadas con el cuerpo del trabajo.",
            "how_to_fix": "",
            "issues": [],
        }

    why_parts = [
        "La bibliografía es trazable: cada cita debe tener entrada y cada entrada debe ser pertinente.",
    ]
    if unmatched:
        why_parts.append("Las citas no emparejadas impiden verificar la fuente de sus afirmaciones.")
    if out_period:
        why_parts.append("Referencias muy anteriores al período metodológico pueden cuestionar pertinencia temporal.")

    how_parts = [
        "Revise el listado detallado en la sección Bibliografía del informe.",
        "Corrija autor/año en texto o complete entradas faltantes.",
    ]
    if doi_warnings:
        how_parts.append("Verifique DOI y URLs rotas o mal escritas.")

    status = "partial" if len(issues) <= 2 and not doi_warnings else "fail"
    if unmatched <= 3 and not doi_warnings:
        status = "partial"

    return {
        "key": "bibliografia",
        "title": SECTION_TITLES["bibliografia"],
        "status": status,
        "ok": False,
        "partial": status == "partial",
        "summary": "Requiere revisión: " + "; ".join(issues) + ".",
        "why": " ".join(why_parts),
        "how_to_fix": " ".join(how_parts),
        "issues": issues,
    }


def build_chapter_reviews(
    structure: dict,
    bib_dashboard: dict,
    warnings_list: list[dict],
    has_objectives: bool,
) -> list[dict]:
    intro = _review_from_checks(
        "introduccion",
        structure.get("introduccion", {}),
        {"problema", "justificación", "pregunta", "objetivos"},
    )

    objectives_block = structure.get("introduccion", {})
    obj_checks = objectives_block.get("checks", [])
    obj_ok = has_objectives or any(c.get("ok") for c in obj_checks if c["label"] == "objetivos")
    objectives = {
        "key": "objetivos",
        "title": SECTION_TITLES["objetivos"],
        "status": "ok" if obj_ok else "fail",
        "ok": obj_ok,
        "partial": False,
        "summary": (
            "Los objetivos específicos están formulados y detectados."
            if obj_ok
            else "No se detectaron objetivos específicos numerados con claridad."
        ),
        "why": CHECK_GUIDANCE["objetivos"]["why"] if not obj_ok else "Los objetivos guían la evaluación de coherencia interna.",
        "how_to_fix": CHECK_GUIDANCE["objetivos"]["how_to_fix"] if not obj_ok else "",
        "checks": obj_checks,
    }

    marco = _review_from_checks(
        "marco_teorico",
        structure.get("marco_teorico", {}),
        {"marco presente", "marco desarrollado", "marco vinculado"},
    )

    metodologia = _review_from_checks(
        "metodologia",
        structure.get("metodologia", {}),
        {"diseño", "muestra", "variables"},
    )

    resultados = _review_from_checks(
        "resultados",
        structure.get("resultados", {}),
        {"resultados presente", "resultados desarrollo"},
    )

    discusion = build_discussion_review(structure.get("discusion", {}))

    conclusiones = _review_from_checks(
        "conclusiones",
        structure.get("conclusiones", {}),
        {"responde objetivos", "responde la pregunta"},
    )

    bibliografia = build_bibliography_review(bib_dashboard, warnings_list)

    return [
        intro,
        objectives,
        marco,
        metodologia,
        resultados,
        discusion,
        conclusiones,
        bibliografia,
    ]


def checklist_status_from_reviews(reviews: list[dict]) -> str:
    core_keys = {"introduccion", "metodologia", "resultados", "discusion", "conclusiones"}
    core_reviews = [r for r in reviews if r["key"] in core_keys]
    secondary = [r for r in reviews if r["key"] not in core_keys]

    core_fails = sum(1 for r in core_reviews if r["status"] == "fail")
    core_ok = sum(1 for r in core_reviews if r["status"] == "ok")
    secondary_issues = sum(1 for r in secondary if not r["ok"])

    if core_fails >= 2:
        return "No apta para presentar"
    if core_fails == 1 or core_ok < len(core_reviews):
        return "Requiere revisión antes de presentar"
    if secondary_issues == 0:
        return "Lista para presentar"
    if secondary_issues <= 3:
        return "Apta con correcciones menores"
    return "Requiere revisión antes de presentar"


def readiness_emoji(status: str) -> str:
    return {
        "Lista para presentar": "✅",
        "Apta con correcciones menores": "⚠",
        "Requiere revisión antes de presentar": "⚠",
        "No apta para presentar": "❌",
    }.get(status, "⚠")
