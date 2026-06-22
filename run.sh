#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  PY="${PYTHON:-python3.11}"
  "$PY" -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/streamlit run app.py
