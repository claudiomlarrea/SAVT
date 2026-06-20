# SAVT — Sistema de Auditoría y Verificación de Tesis

Herramienta institucional para **pre-auditar** tesis (TFI, Maestría, Doctorado) antes de la entrega definitiva.

**Auditor académico** orientado a tesistas, directores y evaluadores: cada hallazgo indica qué significa, por qué importa y cómo corregirlo.

## Funcionalidades (v0.3)

- Parseo de `.docx` y `.pdf`
- **Perfiles institucionales** (UCCuyo, UNCUyo, maestría, doctorado, especialización)
- Escala **ICAI** interpretable (Excelente → No apta)
- Checklist previo a la entrega
- Evaluación orientativa (fortalezas, debilidades, probabilidad de aprobación)
- Estructura académica (introducción, metodología, resultados, discusión, conclusiones)
- Coherencia pregunta → objetivos → resultados → conclusiones
- **Normativa institucional** (portada, resumen, índices, extensión por perfil)
- **Integridad académica** (índice Turnitin/iThenticate + similitud interna)
- **Ética de investigación** (checklist para estudios empíricos)
- **Profundidad académica** (marco teórico, citas, análisis crítico)
- **Originalidad y aporte** (indicadores proxy por nivel de titulación)
- **Preparación para defensa oral** (preguntas probables)
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
│   ├── audit_config.py       # Configuración de auditoría
│   ├── institutional_profiles.py
│   ├── formal_requirements.py
│   ├── integrity.py
│   ├── ethics.py
│   ├── content_quality.py
│   ├── originality.py
│   ├── defense_prep.py
│   ├── report_builder.py
│   └── ...
└── README.md
```

## Uso

1. Abrir la app (local o Streamlit Cloud).
2. Seleccionar **perfil institucional** en la barra lateral.
3. Subir un `.docx` o `.pdf` de tesis.
4. (Opcional) Cargar índice de similitud Turnitin/iThenticate.
5. Ejecutar auditoría.
6. Revisar checklist, normativa, integridad, ética, profundidad y preguntas de defensa.
7. Descargar informe CSV o Word.

## Limitaciones

- No reemplaza evaluación del director ni del jurado.
- Heurísticas sobre texto extraído; en PDF pueden perderse matices.
- Originalidad y profundidad: indicadores proxy, no juicio experto.
- Plagio externo: requiere reporte Turnitin/iThenticate (no hay API integrada).
- Detección de IA: solo si el reporte externo incluye ese dato.

## Licencia

Uso institucional — Universidad Católica de Cuyo / Observatorio de Inteligencia Artificial.
