# Publicar SAVT en GitHub y Streamlit Cloud

## Estado actual

- Repositorio **git local** listo en `main` (commit inicial v0.2).
- **Pendiente:** subir a GitHub (requiere reautenticar `gh`).

## Paso 1 — Reautenticar GitHub CLI

En **Terminal** (fuera de Cursor, si hace falta):

```bash
gh auth login -h github.com --web
```

Elegí: GitHub.com → HTTPS → Login with a web browser.

## Paso 2 — Publicar en GitHub

```bash
cd ~/Documents/Sistema-Auditoria-Verificacion-Tesis
./scripts/publish.sh
```

Si el nombre `SAVT` ya está ocupado:

```bash
./scripts/publish.sh sistema-auditoria-verificacion-tesis
```

Comando manual equivalente:

```bash
cd ~/Documents/Sistema-Auditoria-Verificacion-Tesis
gh repo create SAVT --public --source=. --remote=origin --push
```

## Paso 3 — Desplegar en Streamlit Cloud

1. Entrar en [https://share.streamlit.io](https://share.streamlit.io) con la cuenta de GitHub.
2. Clic en **Create app**.
3. Completar:
   - **Repository:** `claudiomlarrea/SAVT` (o el nombre que haya usado)
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. **Deploy**.

No hace falta configurar secrets para el uso básico. La verificación DOI usa Crossref (API pública).

### Si el deploy falla

- Verificar que `requirements.txt` esté en la raíz.
- Python 3.10 (definido en `.python-version` y `packages.toml`).
- Revisar logs en Streamlit Cloud → Manage app → Logs.
- PyMuPDF puede tardar unos minutos en instalar en el primer deploy.

## Paso 4 — Compartir la app

Tras el deploy, Streamlit asigna una URL como:

`https://savt-claudiomlarrea.streamlit.app`

(El subdominio depende del nombre de la app que elija en el panel.)

## Actualizaciones futuras

Cada cambio que suba a `main` puede redeployarse automáticamente si activó **Auto-redeploy** en Streamlit Cloud:

```bash
cd ~/Documents/Sistema-Auditoria-Verificacion-Tesis
git add .
git commit -m "Descripción del cambio"
git push
```

## Nota sobre privacidad

El `.gitignore` excluye `.pdf` y `.docx` para que no se suban tesis al repositorio. Los usuarios cargan documentos solo en la app en ejecución; no quedan guardados en GitHub.
