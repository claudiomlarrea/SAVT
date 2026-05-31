#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO_NAME="${1:-SAVT}"

echo "==> 1/3 Verificando GitHub CLI..."
if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo ""
  echo "Se requiere iniciar sesión en GitHub (solo una vez)."
  gh auth login -h github.com --web
fi

echo "==> 2/3 Publicando repositorio: $REPO_NAME"
if gh repo view "claudiomlarrea/$REPO_NAME" >/dev/null 2>&1; then
  git push -u origin main
else
  gh repo create "$REPO_NAME" \
    --public \
    --source=. \
    --remote=origin \
    --push \
    --description "SAVT — Sistema de Auditoría y Verificación de Tesis"
fi

REPO_URL="https://github.com/claudiomlarrea/$REPO_NAME"
echo ""
echo "Repositorio: $REPO_URL"

echo ""
echo "==> 3/3 Streamlit Cloud"
echo "Abrí el asistente de despliegue en el navegador."
echo "Completá: Repository = claudiomlarrea/$REPO_NAME | Branch = main | Main file = app.py"
STREAMLIT_URL="https://share.streamlit.io/deploy?repository=claudiomlarrea/$REPO_NAME&branch=main&mainModule=app.py"
if command -v open >/dev/null 2>&1; then
  open "$STREAMLIT_URL" || true
else
  echo "$STREAMLIT_URL"
fi

echo ""
echo "Listo. Cuando termine el deploy, la app estará en una URL *.streamlit.app"
