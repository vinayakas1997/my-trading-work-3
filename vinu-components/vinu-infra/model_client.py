"""Client for the model-serving service (`vinu-models`, docker service `models-api`).

Every component that used to import `torch` itself (the model-category analysis angles in vinu-initial-analysis,
FinBERT scoring in vinu-news) now calls the service instead when `VINU_MODEL_SERVICE_URL` is set. Unset = the old
in-process path, unchanged (callers check `service_url()`).

A failure is never turned into an empty or proxy result: it raises `ModelServiceError` with the reason, so the caller
can record a real error (the analysis runner writes an `error` run, news reports the backfill error).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import pandas as pd

LOG = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 600.0   # training a per-ticker network can take minutes; callers may pass less


class ModelServiceError(RuntimeError):
    """The model service could not produce a result (unreachable, timed out, model unavailable, bad input)."""

    def __init__(self, message: str, *, status: int | None = None, reason: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.reason = reason


def service_url() -> str | None:
    raw = (os.getenv("VINU_MODEL_SERVICE_URL") or "").strip()
    return raw.rstrip("/") or None


def _timeout() -> float:
    try:
        return float(os.getenv("VINU_MODEL_SERVICE_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC))
    except ValueError:
        return DEFAULT_TIMEOUT_SEC


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    import requests

    from vinu_infra.auth import internal_auth_headers

    base = service_url()
    if base is None:
        raise ModelServiceError("VINU_MODEL_SERVICE_URL is not set", reason="not_configured")
    try:
        resp = requests.post(
            f"{base}{path}", data=json.dumps(body, default=str),
            headers={"Content-Type": "application/json", **internal_auth_headers()}, timeout=_timeout(),
        )
    except requests.Timeout as exc:
        raise ModelServiceError(f"model service timed out on {path}", reason="timeout") from exc
    except requests.RequestException as exc:
        raise ModelServiceError(f"model service unreachable at {base}: {exc}", reason="unreachable") from exc
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        reason = detail.get("reason") if isinstance(detail, dict) else None
        raise ModelServiceError(
            f"model service answered {resp.status_code} on {path}: {detail}", status=resp.status_code, reason=reason,
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise ModelServiceError(f"model service returned non-JSON on {path}", reason="bad_response") from exc


def _frame_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or len(df) == 0:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def compute_angle(
    angle: str, *, symbol: str, bars: pd.DataFrame | None, news: list[dict] | None,
    from_ts: int | None, to_ts: int | None, time_format: str | None,
) -> pd.DataFrame:
    """Run one model-category angle's `compute()` inside the model service and return its DataFrame."""
    out = _post(f"/models/angle/{angle}/compute", {
        "symbol": symbol, "bars": _frame_to_records(bars), "news": news or [],
        "from_ts": from_ts, "to_ts": to_ts, "time_format": time_format,
    })
    rows = out.get("rows")
    if not isinstance(rows, list):
        raise ModelServiceError(f"model service result for {angle} has no 'rows' list", reason="bad_response")
    return pd.DataFrame(rows)


def score_finbert(texts: list[str], batch_size: int = 16) -> list[dict]:
    out = _post("/models/finbert/score", {"texts": texts, "batch_size": batch_size})
    results = out.get("results")
    if not isinstance(results, list) or len(results) != len(texts):
        raise ModelServiceError("model service FinBERT result does not match the request", reason="bad_response")
    return results
