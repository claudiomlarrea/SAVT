from __future__ import annotations

import re

from savt.models import Finding


def audit_coherence(parsed: dict) -> list[Finding]:
    """Coherencia metodológica y advertencias transversales (sin duplicar pregunta/objetivos)."""
    findings: list[Finding] = []
    body = parsed["body"].lower()

    if re.search(r"revisión bibliográfica integradora", body):
        if re.search(r"pacientes propios|muestra de \d+|ensayo clínico propio|recolección primaria", body):
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="warning",
                    area="Coherencia",
                    title="Posible inconsistencia metodológica",
                    detail=(
                        "El trabajo se declara revisión bibliográfica, pero el texto sugiere "
                        "recolección primaria o análisis estadístico propio."
                    ),
                    why="El tipo de estudio declarado debe coincidir con lo que realmente se hizo.",
                    how_to_fix="Ajuste la formulación metodológica o el contenido para que sean coherentes.",
                )
            )
        else:
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="ok",
                    area="Coherencia",
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
                    area="Coherencia",
                    title="Posible inconsistencia metodológica",
                    detail="El texto combina enfoque empírico con formulaciones de revisión bibliográfica exclusiva.",
                    why="Mezclar enfoques sin explicitarlos confunde al evaluador.",
                    how_to_fix="Aclare si el estudio es empírico, documental o mixto.",
                )
            )
        else:
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="ok",
                    area="Coherencia",
                    title="Coherencia metodológica empírica",
                    detail="Se detecta un estudio con componente empírico/analítico coherente con el contenido.",
                )
            )

    if re.search(r"2020", body) and re.search(r"2026", body) and re.search(r"2023", body):
        if re.search(r"2020.{0,10}2026", body) and re.search(r"2020.{0,10}2023", body):
            findings.append(
                Finding(
                    module="Coherencia",
                    severity="info",
                    area="Metodología",
                    title="Rangos temporales distintos en metodología y bibliometría",
                    detail=(
                        "La metodología menciona un rango temporal distinto al análisis bibliométrico. "
                        "Conviene justificar o unificar el criterio."
                    ),
                    why="Rangos distintos pueden interpretarse como falta de rigor metodológico.",
                    how_to_fix="Unifique el período o explique por qué difieren metodología y bibliometría.",
                )
            )

    return findings
