from typing import Any

from ..agent.tools import BaseTool

# Per-angle digest bounds: each angle's own row schema is different (trend
# fields, regime fields, backtest metrics, ...), so there's no single fixed
# shape to parse -- this takes every scalar field the freshest row actually
# has (no per-angle field cap: an early cap risks silently dropping an
# angle's actual signal fields behind boilerplate like symbol/timestamp/id
# that happens to come first in the row). Still bounded on the two axes
# that guard against a genuinely pathological entry: an absurdly long
# string field, and the total number of angles carried.
_DIGEST_MAX_STRING_LEN = 200
_DIGEST_MAX_ANGLES = 30


def summarize_angle(angle_name: str, angle_result: dict) -> dict | None:
    """Freshest-row, scalar-fields-only digest of one angle's `execute()`
    entry. Returns None when there's nothing informative to add (no data,
    an error entry, or a malformed row) -- best-effort, never raises."""
    try:
        if not isinstance(angle_result, dict):
            return None
        if angle_result.get("row_count", 0) <= 0 or angle_result.get("error"):
            return None
        rows = angle_result.get("data")
        if not isinstance(rows, list) or not rows:
            return None
        last_row = rows[-1]
        if not isinstance(last_row, dict):
            return None
        digest: dict[str, Any] = {}
        for key, value in last_row.items():
            if isinstance(value, bool) or isinstance(value, (int, float)):
                digest[key] = value
            elif isinstance(value, str) and len(value) <= _DIGEST_MAX_STRING_LEN:
                digest[key] = value
        return digest or None
    except Exception:
        return None


def build_angle_digest(angles_data: dict) -> dict:
    """Runs summarize_angle over every angle in a `GetAllAnglesTool.execute()`
    result, keeping only the angles that had something to say."""
    digest: dict[str, dict] = {}
    try:
        angles = angles_data.get("angles") or {}
        for name, result in angles.items():
            if len(digest) >= _DIGEST_MAX_ANGLES:
                break
            summarized = summarize_angle(name, result)
            if summarized is not None:
                digest[name] = summarized
    except Exception:
        return digest
    return digest


class GetAllAnglesTool(BaseTool):
    name = "get_all_angles"
    description = (
        "Fetch every vinu-initial-analysis angle's latest computed result for one ticker, "
        "in a single call. Angles with no data yet are reported as such (row_count=0), "
        "not omitted -- always check row_count before treating an angle as informative."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL"},
        },
        "required": ["ticker"],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import json
        import httpx
        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None

        ticker = kwargs["ticker"].strip().upper()
        base = self._services_config.get("vinu_initial_analysis", "http://localhost:8083").rstrip("/")
        url = f"{base}/analysis"
        v1_base = f"{base}/v1/stage1/vinu-initial-analysis"
        # Full window 2022-01-01 uses tier3 v1 fetch 1day 2022-01-01_2026-07-01
        import os
        stage1 = os.getenv("VINU_STAGE1_START_DATE", "2022-01-01")
        time_range = f"{stage1}T00:00:00Z_2026-07-01T00:00:00Z"

        with httpx.Client(timeout=60.0, headers=_h) as client:
            angles_resp = client.get(f"{url}/angles")
            angles_resp.raise_for_status()
            angle_names = [a["name"] for a in angles_resp.json().get("angles", [])]

            results = {}
            for name in angle_names:
                # Try Full window v1 tier3 first when stage1 is 2022
                v1_ok = False
                if stage1 == "2022-01-01":
                    try:
                        v1_resp = client.get(f"{v1_base}/fetch/{ticker}/1day/{time_range}/{name}")
                        if v1_resp.status_code == 200:
                            j = v1_resp.json()
                            data = j.get("data") or []
                            # v1 returns Envelope tier3 with data list
                            if isinstance(data, list) and data:
                                rec = data[0]
                                results[name] = {
                                    "symbol": ticker, "angle": name,
                                    "row_count": len(data),
                                    "data": data,
                                    "status": rec.get("status", "ok"),
                                    "tier": j.get("tier", "tier3"),
                                }
                                v1_ok = True
                            elif data:
                                results[name] = {"symbol": ticker, "angle": name, "row_count": 1, "data": data, "tier": "tier3"}
                                v1_ok = True
                    except Exception:
                        v1_ok = False
                if not v1_ok:
                    try:
                        resp = client.get(f"{url}/angle/{name}/{ticker}")
                        resp.raise_for_status()
                        results[name] = resp.json()
                    except Exception as exc:
                        results[name] = {"symbol": ticker, "angle": name, "error": str(exc), "row_count": 0, "data": []}

        with_data = sum(1 for r in results.values() if r.get("row_count", 0) > 0)
        return json.dumps({
            "ticker": ticker,
            "angle_count": len(angle_names),
            "angles_with_data": with_data,
            "angles": results,
        })
