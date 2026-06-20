from __future__ import annotations

import re

from savt.models import Finding

SOURCE_HINTS = ["fuente:", "elaboración propia", "elaboracion propia", "adaptado de", "tomado de"]

CAPTION_PATTERNS = [
    (r"(?im)^\s*Figura\s+(\d+)(?:\s*N[º°o]\.?|:|\.)\s*(.+)$", "Figura"),
    (r"(?im)^\s*Figura\s+(\d+)\.\s*(.+)$", "Figura"),
    (r"(?im)^\s*Fig\.\s*(\d+)(?:\s*N[º°o]\.?|:|\.)\s*(.+)$", "Figura"),
    (r"(?im)^\s*Fig\.\s*(\d+)\.\s*(.+)$", "Figura"),
    (r"(?im)^\s*Figure\s+(\d+)(?:\s*N[º°o]\.?|:|\.)\s*(.+)$", "Figure"),
    (r"(?im)^\s*Figure\s+(\d+)\.\s*(.+)$", "Figure"),
    (r"(?im)^\s*Gr[aá]fico\s+(\d+)(?:\s*N[º°o]\.?|:|\.)\s*(.+)$", "Gráfico"),
    (r"(?im)^\s*Gr[aá]fico\s+(\d+)\.\s*(.+)$", "Gráfico"),
    (r"(?im)^\s*Cuadro\s+(\d+)(?:\s*N[º°o]\.?|:|\.)\s*(.+)$", "Cuadro"),
    (r"(?im)^\s*Cuadro\s+(\d+)\.\s*(.+)$", "Cuadro"),
    (r"(?im)^\s*Imagen\s+(\d+)(?:\s*N[º°o]\.?|:|\.)\s*(.+)$", "Imagen"),
    (r"(?im)^\s*Imagen\s+(\d+)\.\s*(.+)$", "Imagen"),
]


def _collect_captions(body: str) -> dict[int, tuple[str, str]]:
    caption_map: dict[int, tuple[str, str]] = {}
    for pattern, kind in CAPTION_PATTERNS:
        for num, title in re.findall(pattern, body):
            number = int(num)
            if number not in caption_map:
                caption_map[number] = (kind, title.strip())
    return caption_map


def analyze_figures(body: str) -> tuple[list[dict], list[Finding]]:
    findings: list[Finding] = []
    caption_map = _collect_captions(body)
    caption_nums = sorted(caption_map.keys())
    details: list[dict] = []

    if not caption_nums:
        informal = len(re.findall(r"\bgr[aá]fico\b", body, re.I))
        if informal >= 3:
            findings.append(
                Finding(
                    module="Figuras",
                    severity="info",
                    area="Figuras y tablas",
                    title="Visualizaciones mencionadas sin numeración estándar",
                    detail=(
                        f"Se detectaron ~{informal} menciones a gráficos sin leyenda "
                        "'Figura N.' / 'Gráfico N.'. Conviene numerar y citar en el texto."
                    ),
                )
            )
        else:
            findings.append(
                Finding(
                    module="Figuras",
                    severity="info",
                    area="Figuras y tablas",
                    title="No se detectaron figuras numeradas",
                    detail="Si el trabajo incluye figuras, use leyendas 'Figura N.' o 'Gráfico N.'",
                )
            )
        return details, findings

    lines = body.splitlines()
    for num in caption_nums:
        kind, title = caption_map[num]
        mention_patterns = [
            rf"\b{kind}\s+{num}\b",
            rf"\bFigura\s+{num}\b",
            rf"\bFig\.\s*{num}\b",
            rf"\bGr[aá]fico\s+{num}\b",
            rf"\b{kind}\s+{num}\s*N",
        ]
        mentioned = any(
            re.search(p, line, re.IGNORECASE)
            for line in lines
            if not re.match(rf"^\s*{kind}\s+{num}\.", line.strip(), re.IGNORECASE)
            for p in mention_patterns
        )

        context = title
        has_source = any(h in title.lower() for h in SOURCE_HINTS) or "http" in title.lower()

        details.append(
            {
                "number": num,
                "title": f"{kind} {num}. {title}",
                "has_number": True,
                "has_title": len(title) > 5,
                "cited_in_text": mentioned,
                "has_source": has_source,
            }
        )

    uncited = [d["number"] for d in details if not d["cited_in_text"]]
    if uncited:
        findings.append(
            Finding(
                module="Figuras",
                severity="warning",
                area="Figuras y tablas",
                title="Figuras no citadas en el texto",
                detail="Algunas figuras tienen leyenda pero no se mencionan en el cuerpo.",
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

    return details, findings
