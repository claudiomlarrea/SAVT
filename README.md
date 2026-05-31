# SAVT — Sistema de Auditoría y Verificación de Tesis

Herramienta institucional para auditar tesis (TFI, Maestría, Doctorado) antes de la entrega definitiva.

**Auditor académico** orientado a tesistas, directores y evaluadores: cada hallazgo indica qué significa, por qué importa y cómo corregirlo.

## Funcionalidades (v0.2)

- Parseo de `.docx` y `.pdf`
- Escala **ICAI** interpretable (Excelente → No apta)
- Checklist previo a la entrega
- Evaluación como jurado (fortalezas, debilidades, probabilidad de aprobación)
- Estructura académica (introducción, metodología, resultados, discusión, conclusiones)
- Coherencia pregunta → objetivos → resultados → conclusiones
- Bibliografía APA y Vancouver numerado
- Figuras y tablas (numeración, cita, fuente)
- Validación DOI via Crossref (opcional)

## Requisitos

- Python 3.10+
- macOS / Linux / Windows

## Instalación local

```bash
git clone https://github.com/claudiomlarrea/SAVT.git
cd SAVT
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

La app queda en `http://localhost:8501`.

## Despliegue en Streamlit Cloud

1. Subir este repositorio a GitHub (rama `main`).
2. Entrar en [share.streamlit.io](https://share.streamlit.io) con la cuenta de GitHub.
3. **New app** → seleccionar el repo `SAVT`.
4. Configuración:
   - **Main file path:** `app.py`
   - **Branch:** `main`
   - **Python version:** 3.10 o superior
5. Deploy.

No se requieren secrets para el funcionamiento básico. La verificación DOI usa la API pública de Crossref.

## Estructura

```text
SAVT/
├── app.py                    # Interfaz Streamlit
├── requirements.txt
├── packages.toml             # Versión Python para Streamlit Cloud
├── savt/
│   ├── audit.py              # Orquestador
│   ├── report_builder.py     # Informe académico
│   ├── structure.py          # Estructura de capítulos
│   ├── objectives_coherence.py
│   ├── research_question.py
│   ├── parser.py / pdf_parser.py
│   ├── citations.py
│   ├── figures.py / tables.py
│   └── ...
└── README.md
```

## Uso

1. Abrir la app (local o Streamlit Cloud).
2. Subir un `.docx` o `.pdf` de tesis.
3. Ejecutar auditoría.
4. Revisar checklist, qué corregir primero y evaluación como jurado.
5. Descargar informe CSV.

## Limitaciones

- No reemplaza evaluación del director ni del jurado.
- Heurísticas sobre texto extraído; en PDF pueden perderse matices.
- Plagio externo e IA: pendiente de integración con servicios especializados.

## Licencia

Uso institucional — Universidad del Salvador / Secretaría de Investigación.
