"""Contador de auditorías SAVT (local y opcional remoto vía secrets)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_COUNTER_PATH = Path(__file__).resolve().parent.parent / ".savt_usage" / "counter.json"
_USER_AGENT = "SAVT-UsageCounter/1.0"


def _read_local_count() -> int:
    if not _COUNTER_PATH.exists():
        return 0
    try:
        data = json.loads(_COUNTER_PATH.read_text(encoding="utf-8"))
        return max(0, int(data.get("count", 0)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def _write_local_count(count: int) -> int:
    _COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"count": count}, ensure_ascii=False)
    tmp_path = _COUNTER_PATH.with_suffix(".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(_COUNTER_PATH)
    return count


def _secrets_usage() -> dict:
    try:
        import streamlit as st

        return dict(st.secrets.get("usage", {}))
    except Exception:
        return {}


def _fetch_remote_count(url: str, method: str = "GET") -> int | None:
    request = Request(
        url,
        method=method,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json, text/plain"},
    )
    with urlopen(request, timeout=5) as response:
        body = response.read().decode("utf-8", errors="replace").strip()
    if not body:
        return None
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            for key in ("count", "value", "total"):
                if key in data:
                    return max(0, int(data[key]))
        return max(0, int(data))
    except (TypeError, ValueError, json.JSONDecodeError):
        return max(0, int(body))


def _try_remote(hit: bool) -> int | None:
    usage = _secrets_usage()
    if hit:
        url = usage.get("increment_url") or usage.get("url")
        method = str(usage.get("increment_method", "POST")).upper()
    else:
        url = usage.get("get_url") or usage.get("url")
        method = "GET"
    if not url:
        return None
    return _fetch_remote_count(url, method=method)


def _try_local(hit: bool) -> int:
    count = _read_local_count()
    if hit:
        count += 1
        _write_local_count(count)
    return count


def record_audit_usage() -> int | None:
    """Incrementa el contador tras una auditoría exitosa. Nunca lanza excepciones."""
    for backend in (_try_remote, _try_local):
        try:
            if backend is _try_remote:
                count = backend(hit=True)
                if count is not None:
                    return count
                continue
            return backend(hit=True)
        except (OSError, URLError, ValueError, TypeError) as exc:
            logger.debug("No se pudo registrar uso SAVT (%s): %s", backend.__name__, exc)
    return None


def get_usage_count() -> int | None:
    """Devuelve el total de auditorías registradas sin incrementar."""
    for backend in (_try_remote, _try_local):
        try:
            if backend is _try_remote:
                count = backend(hit=False)
                if count is not None:
                    return count
                continue
            return backend(hit=False)
        except (OSError, URLError, ValueError, TypeError) as exc:
            logger.debug("No se pudo leer uso SAVT (%s): %s", backend.__name__, exc)
    return None
