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
4. **Advanced settings** → **Python version: 3.11** (obligatorio; no usar 3.14).
5. **Deploy**.

No hace falta configurar secrets para el uso básico. La verificación DOI usa Crossref (API pública).

### Si el deploy falla o queda en "Your app is in the oven"

El error más común en los logs es:

```text
Using Python 3.14.x environment
× Failed to download and build `pyarrow==...`
error: command 'cmake' failed: No such file or directory
```

**Causa:** Streamlit Cloud eligió Python **3.14** por defecto. `pyarrow` y `pandas` no tienen wheels para 3.14 y el build falla.

**Solución (la única que funciona hoy):**

1. **Borrá la app** en share.streamlit.io (no alcanza con Reboot).
2. **Create app** de nuevo con los mismos datos.
3. En **Advanced settings** elegí **Python 3.11**.
4. Deploy y esperá 5–10 minutos.

`packages.toml` y `.python-version` **no** cambian la versión en Streamlit Cloud: solo cuenta la que elegís en Advanced settings al crear la app.

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
