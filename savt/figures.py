from __future__ import annotations

import re

from savt.models import Finding

SOURCE_HINTS = ["fuente:", "elaboración propia", "elaboracion propia", "adaptado de", "tomado de"]


def analyze_figures(body: str) -> tuple[list[dict], list[Finding]]:
    findings: list[Finding] = []
    captions = re.findall(r"(?im)^\s*Figura\s+(\d+)\.\s*(.+)$", body)
    caption_map = {int(num): title.strip() for num, title in captions}
    caption_nums = sorted(caption_map.keys())
    details: list[dict] = []

    if not caption_nums:
        findings.append(
            Finding(
                module="Figuras",
                severity="info",
                area="Figuras y tablas",
                title="No se detectaron figuras numeradas",
                detail="Si la tesis incluye figuras, verifique leyendas con formato 'Figura N.'",
            )
        )
        return details, findings

    lines = body.splitlines()
    for num in caption_nums:
        title = caption_map[num]
        mention_patterns = [
            rf"\bFigura\s+{num}\b",
            rf"\bfigura\s+{num}\b",
            rf"\bFig\.\s*{num}\b",
        ]
        mentioned = False
        for line in lines:
            if re.match(rf"^\s*Figura\s+{num}\.", line.strip(), re.IGNORECASE):
                continue
            if any(re.search(p, line, re.IGNORECASE) for p in mention_patterns):
                mentioned = True
                break

        caption_idx = None
        for idx, line in enumerate(lines):
            if re.match(rf"^\s*Figura\s+{num}\.", line.strip(), re.IGNORECASE):
                caption_idx = idx
                break
        context = "\n".join(lines[caption_idx : caption_idx + 4]) if caption_idx is not None else title
        has_source = any(h in context.lower() for h in SOURCE_HINTS) or "http" in context.lower()

        item = {
            "number": num,
            "title": title,
            "has_number": True,
            "has_title": len(title) > 5,
            "cited_in_text": mentioned,
            "has_source": has_source,
        }
        details.append(item)

    uncited = [d["number"] for d in details if not d["cited_in_text"]]
    no_source = [d["number"] for d in details if not d["has_source"]]

    if uncited:
        findings.append(
            Finding(
                module="Figuras",
                severity="warning",
                area="Figuras y tablas",
                title="Figuras no citadas en el texto",
                detail="Algunas figuras tienen leyenda pero no se mencionan en párrafos del cuerpo.",
                evidence=f"Figuras: {uncited}",
                why="Toda figura debe integrarse al argumento del texto.",
                how_to_fix="Mencione cada figura antes de presentarla o al interpretarla.",
            )
        )
    else:
        findings.append(
            Finding(
                module="Figuras",
                severity="ok",
                area="Figuras y tablas",
                title="Figuras citadas en el texto",
                detail=f"Las {len(details)} figuras detectadas están referenciadas en el cuerpo.",
            )
        )

    if no_source:
        findings.append(
            Finding(
                module="Figuras",
                severity="info",
                area="Figuras y tablas",
                title="Figuras sin fuente indicada",
                detail="Algunas leyendas no incluyen fuente o elaboración propia.",
                evidence=f"Figuras: {no_source}",
                how_to_fix="Agregue 'Fuente: …' o 'Elaboración propia' bajo cada figura.",
            )
        )

    expected = list(range(1, max(caption_nums) + 1))
    gaps = [n for n in expected if n not in caption_nums]
    if gaps:
        findings.append(
            Finding(
                module="Figuras",
                severity="warning",
                area="Figuras y tablas",
                title="Numeración de figuras discontinua",
                detail=f"Faltan figuras en la secuencia: {gaps}",
            )
        )

    return details, findings


def audit_figures(body: str) -> list[Finding]:
    _, findings = analyze_figures(body)
    return findings
