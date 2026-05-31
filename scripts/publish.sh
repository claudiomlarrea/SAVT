#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO_NAME="${1:-SAVT}"

echo "==> Verificando autenticación GitHub..."
if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "No hay sesión válida en GitHub CLI."
  echo "Ejecute primero: gh auth login -h github.com"
  exit 1
fi

echo "==> Creando repositorio remoto: $REPO_NAME"
if gh repo view "claudiomlarrea/$REPO_NAME" >/dev/null 2>&1; then
  echo "El repositorio ya existe. Configurando remote..."
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/claudiomlarrea/$REPO_NAME.git"
else
  gh repo create "$REPO_NAME" \
    --public \
    --source=. \
    --remote=origin \
    --description "SAVT — Sistema de Auditoría y Verificación de Tesis (auditor académico institucional)"
fi

echo "==> Subiendo rama main..."
git push -u origin main

echo ""
echo "Repositorio publicado:"
gh repo view "claudiomlarrea/$REPO_NAME" --json url -q .url
echo ""
echo "Siguiente paso — Streamlit Cloud:"
echo "1. Abrir https://share.streamlit.io"
echo "2. New app → repo claudiomlarrea/$REPO_NAME"
echo "3. Main file: app.py | Branch: main"
echo "4. Deploy"
