# Publicar SAVT en GitHub y Streamlit Cloud

## Estado actual

- Repositorio publicado: https://github.com/claudiomlarrea/SAVT
- **Pendiente:** desplegar o redeploy en Streamlit Cloud (la app `savt-claudiomlarrea.streamlit.app` devuelve 404 si aún no se creó o falló el deploy).

## Instalación local (desde cero)

```bash
git clone https://github.com/claudiomlarrea/SAVT.git
cd SAVT
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Requisito: Python **3.10+** (recomendado 3.11, ver `.python-version`).

## Paso 1 — Desplegar en Streamlit Cloud

1. Entrar en [https://share.streamlit.io](https://share.streamlit.io) con la cuenta de GitHub.
2. Clic en **Create app**.
3. Completar:
   - **Repository:** `claudiomlarrea/SAVT`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. **Deploy** (Python 3.11 o 3.14; las dependencias actuales soportan ambos).

No hace falta configurar secrets para el uso básico. La verificación DOI usa Crossref (API pública).

### Si el deploy falla o queda en "Your app is in the oven"

Si los logs muestran error al compilar `pyarrow` o `pandas` (p. ej. `cmake failed`), la app se creó con dependencias viejas. Hacé **Reboot app** después de un `git push` reciente, o borrá la app y volvé a desplegar.

El primer deploy puede tardar **5–10 minutos** (PyMuPDF es pesado). Esperá a ver en los logs:

```text
Processed dependencies!
```

y luego que arranque el servidor.

## Paso 2 — Compartir la app

Tras el deploy, Streamlit asigna una URL como:

`https://savt-claudiomlarrea.streamlit.app`

(El subdominio depende del nombre de la app que elija en el panel.)

## Actualizaciones futuras

Cada cambio que suba a `main` puede redeployarse automáticamente si activó **Auto-redeploy** en Streamlit Cloud:

```bash
cd SAVT
git add .
git commit -m "Descripción del cambio"
git push
```

## Nota sobre privacidad

El `.gitignore` excluye `.pdf` y `.docx` para que no se suban tesis al repositorio. Los usuarios cargan documentos solo en la app en ejecución; no quedan guardados en GitHub.
