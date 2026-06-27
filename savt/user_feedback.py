"""Envío de valoraciones de usuarios (Google Sheets vía Apps Script o respaldo local)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_FEEDBACK_PATH = Path(__file__).resolve().parent.parent / ".savt_usage" / "feedback.jsonl"
_USER_AGENT = "SAVT-Feedback/1.0"


def _secrets_feedback() -> dict:
    try:
        import streamlit as st

        return dict(st.secrets.get("feedback", {}))
    except Exception:
        return {}


def _append_local(payload: dict) -> bool:
    _FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False)
    with _FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return True


def _submit_remote(payload: dict) -> bool:
    feedback = _secrets_feedback()
    url = feedback.get("submit_url") or feedback.get("url")
    if not url:
        return False

    body = dict(payload)
    token = feedback.get("token")
    if token:
        body["token"] = token

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=str(feedback.get("method", "POST")).upper(),
        headers={
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8", errors="replace").strip()
    if not raw:
        return True
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return bool(parsed.get("ok", True))
    except json.JSONDecodeError:
        pass
    return True


def submit_user_feedback(
    rating: int,
    comment: str,
    *,
    version: str = "",
    filename: str = "",
    icai: int | None = None,
    profile: str = "",
) -> tuple[bool, str]:
    """Guarda la valoración del usuario. Devuelve (éxito, mensaje)."""
    rating = int(rating)
    if rating < 1 or rating > 5:
        return False, "La calificación debe estar entre 1 y 5."

    comment = (comment or "").strip()
    if len(comment) > 4000:
        comment = comment[:4000]

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rating": rating,
        "comment": comment,
        "version": version,
        "filename": filename,
        "icai": icai if icai is not None else "",
        "profile": profile,
        "source": "savt-streamlit",
    }

    for backend_name, backend in (("remote", _submit_remote), ("local", _append_local)):
        try:
            if backend(payload):
                if backend_name == "remote":
                    return True, "Gracias. Su valoración fue registrada."
                return True, "Gracias. Valoración guardada localmente (modo desarrollo)."
        except (OSError, URLError, ValueError, TypeError) as exc:
            logger.debug("No se pudo enviar feedback SAVT (%s): %s", backend_name, exc)

    return False, "No se pudo registrar la valoración. Intente más tarde."
