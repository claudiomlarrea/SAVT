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
   - **Repository:** `claudiomlarrea/SAVT` (o el nombre que haya usado)
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. **Deploy**.

No hace falta configurar secrets para el uso básico. La verificación DOI usa Crossref (API pública).

### Si el deploy falla

- Verificar que `requirements.txt` esté en la raíz y que las versiones existan en PyPI (p. ej. `streamlit==1.50.0`, no versiones inventadas).
- En **Advanced settings**, elegir Python **3.11** (coincide con `.python-version` y `packages.toml`).
- Revisar logs en Streamlit Cloud → Manage app → Logs.
- PyMuPDF puede tardar unos minutos en instalar en el primer deploy.

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
