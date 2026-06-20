from __future__ import annotations

import re

from savt.models import Finding

SOURCE_HINTS = ["fuente:", "elaboración propia", "elaboracion propia", "adaptado de", "tomado de"]


def analyze_tables(body: str) -> tuple[list[dict], list[Finding]]:
    findings: list[Finding] = []
    captions = re.findall(r"(?im)^\s*(?:Tabla|Table)\s+(\d+)\.\s*(.+)$", body)
    caption_map = {int(num): title.strip() for num, title in captions}
    caption_nums = sorted(caption_map.keys())
    details: list[dict] = []

    if not caption_nums:
        findings.append(
            Finding(
                module="Tablas",
                severity="info",
                area="Figuras y tablas",
                title="No se detectaron tablas numeradas",
                detail="Si la tesis incluye tablas, verifique leyendas con formato 'Tabla N.'",
            )
        )
        return details, findings

    lines = body.splitlines()
    for num in caption_nums:
        title = caption_map[num]
        mention_patterns = [
            rf"\bTabla\s+{num}\b",
            rf"\btabla\s+{num}\b",
            rf"\bTab\.\s*{num}\b",
        ]
        mentioned = False
        for line in lines:
            if re.match(rf"^\s*Tabla\s+{num}\.", line.strip(), re.IGNORECASE):
                continue
            if any(re.search(p, line, re.IGNORECASE) for p in mention_patterns):
                mentioned = True
                break

        caption_idx = None
        for idx, line in enumerate(lines):
            if re.match(rf"^\s*Tabla\s+{num}\.", line.strip(), re.IGNORECASE):
                caption_idx = idx
                break
        context = "\n".join(lines[caption_idx : caption_idx + 4]) if caption_idx is not None else title
        has_source = any(h in context.lower() for h in SOURCE_HINTS)

        details.append(
            {
                "number": num,
                "title": title,
                "has_number": True,
                "has_title": len(title) > 5,
                "cited_in_text": mentioned,
                "has_source": has_source,
            }
        )

    uncited = [d["number"] for d in details if not d["cited_in_text"]]
    no_source = [d["number"] for d in details if not d["has_source"]]

    if uncited:
        findings.append(
            Finding(
                module="Tablas",
                severity="warning",
                area="Figuras y tablas",
                title="Tablas no mencionadas en el texto",
                detail="Algunas tablas tienen leyenda pero no se referencian en párrafos.",
                evidence=f"Tablas: {uncited}",
                how_to_fix="Mencione cada tabla al presentar o interpretar sus datos.",
            )
        )
    else:
        findings.append(
            Finding(
                module="Tablas",
                severity="ok",
                area="Figuras y tablas",
                title="Tablas referenciadas en el texto",
                detail=f"Las {len(details)} tablas detectadas están mencionadas en el cuerpo.",
            )
        )

    if no_source:
        findings.append(
            Finding(
                module="Tablas",
                severity="info",
                area="Figuras y tablas",
                title="Tablas sin fuente indicada",
                detail="Algunas tablas no incluyen fuente o elaboración propia.",
                evidence=f"Tablas: {no_source}",
            )
        )

    return details, findings


def audit_tables(body: str) -> list[Finding]:
    _, findings = analyze_tables(body)
    return findings
