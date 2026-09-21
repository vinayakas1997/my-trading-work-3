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


# v1 API path segments only cover these 6 (routes_v1.py's own
# _GRANULARITY_MAP) -- a couple of real angles (backtesting_44_metrics,
# regime_analysis) also declare "1W"/"1M"/"6M" in angles.yaml, which the
# v1 fetch route has no URL segment for at all. Anything not in this map
# skips the v1 attempt entirely and goes straight to the fallback route,
# which accepts any raw granularity string as a query param.
_V1_GRANULARITY_SEGMENTS = {
    "1min": "1min", "5min": "5min", "15min": "15min",
    "1H": "1hr", "4H": "4hr", "1D": "1day",
}


def _fetch_angle_results(
    client, url: str, v1_base: str, ticker: str, time_format: str,
    angle_names: list[str], time_range: str, stage1: str,
) -> dict:
    """Real per-angle fetch loop (v1 tier3 first, fallback route second) --
    shared by `GetAllAnglesTool` (all 28 angles) and `GetClusterAnglesTool`
    (one cluster's own real members only), so the two tools can't drift on
    how a result is actually fetched."""
    v1_segment = _V1_GRANULARITY_SEGMENTS.get(time_format)
    results = {}
    for name in angle_names:
        v1_ok = False
        if stage1 == "2022-01-01" and v1_segment is not None:
            try:
                v1_resp = client.get(f"{v1_base}/fetch/{ticker}/{v1_segment}/{time_range}/{name}")
                if v1_resp.status_code == 200:
                    j = v1_resp.json()
                    data = j.get("data") or []
                    if isinstance(data, list) and data:
                        results[name] = {
                            "symbol": ticker, "angle": name,
                            "row_count": len(data),
                            "data": data,
                            "status": data[0].get("status", "ok"),
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
                resp = client.get(f"{url}/angle/{name}/{ticker}", params={"granularity": time_format})
                resp.raise_for_status()
                results[name] = resp.json()
            except Exception as exc:
                results[name] = {"symbol": ticker, "angle": name, "error": str(exc), "row_count": 0, "data": []}
    return results


class GetAllAnglesTool(BaseTool):
    name = "get_all_angles"
    description = (
        "Fetch every vinu-initial-analysis angle's latest computed result for one ticker, "
        "in a single call. Angles with no data yet are reported as such (row_count=0), "
        "not omitted -- always check row_count before treating an angle as informative. "
        "Defaults to daily (1D) data; pass time_format to fetch a different real "
        "granularity instead -- e.g. '1H' to check whether a shorter-term read confirms "
        "or diverges from the daily picture. Not every angle declares every timeframe "
        "(see each angle's real time_formats list); a timeframe an angle doesn't support "
        "reports as no data for that angle, same as any other missing-data case."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL"},
            "time_format": {
                "type": "string",
                "description": (
                    "Real granularity to fetch, e.g. '1min', '5min', '15min', '1H', "
                    "'4H', '1D', '1W', '1M', '6M' -- matches the angle's own declared "
                    "time_formats. Defaults to '1D' (today's only behavior before this "
                    "parameter existed)."
                ),
            },
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
        time_format = str(kwargs.get("time_format") or "1D").strip()
        base = self._services_config.get("vinu_initial_analysis", "http://localhost:8083").rstrip("/")
        url = f"{base}/analysis"
        v1_base = f"{base}/v1/stage1/vinu-initial-analysis"
        # Full window 2022-01-01 uses tier3 v1 fetch {segment} 2022-01-01_2026-07-01
        import os
        stage1 = os.getenv("VINU_STAGE1_START_DATE", "2022-01-01")
        time_range = f"{stage1}T00:00:00Z_2026-07-01T00:00:00Z"

        with httpx.Client(timeout=60.0, headers=_h) as client:
            angles_resp = client.get(f"{url}/angles")
            angles_resp.raise_for_status()
            angle_names = [a["name"] for a in angles_resp.json().get("angles", [])]
            results = _fetch_angle_results(
                client, url, v1_base, ticker, time_format, angle_names, time_range, stage1,
            )

        with_data = sum(1 for r in results.values() if r.get("row_count", 0) > 0)
        return json.dumps({
            "ticker": ticker,
            "time_format": time_format,
            "angle_count": len(angle_names),
            "angles_with_data": with_data,
            "angles": results,
        })


class GetClusterAnglesTool(BaseTool):
    """Real, structural version of `get_all_angles` scoped to ONE of the 7
    real clusters -- built after real live-LLM testing
    (missing-pieces-of-system/angle-comprehension-hierarchy/
    03-real-llm-findings-and-guardrails.md) confirmed that a synthesis
    given ALL 28 angles at once will sometimes cite an angle under the
    wrong cluster (a real, confirmed hallucination: `kalman_filters`, a
    real Cluster A member, cited inside a Cluster B synthesis). Scoping
    the tool result itself -- not just the prompt instructions -- means a
    specialist handling one cluster never has another cluster's angle
    data in its context at all, so that mistake becomes structurally
    impossible rather than merely discouraged. Also real testing found
    this fully fixed the angle-coverage miscounting problem (7 of 7
    clusters exactly correct vs. 0 of 2 runs correct for the all-28-at-
    once version) at no measured latency cost, since each call fetches
    far fewer angles.
    """

    name = "get_cluster_angles"
    description = (
        "Fetch one real cluster's own angles' latest computed results for one ticker -- "
        "the same real data get_all_angles returns, but scoped to only the real members "
        "of the one cluster you name (A-G). Use this instead of get_all_angles when "
        "you've been asked to synthesize just one cluster -- it never returns another "
        "cluster's angles, so there's no way to accidentally cite the wrong cluster's "
        "angle. Defaults to daily (1D) data; pass time_format for a different real "
        "granularity, same as get_all_angles."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL"},
            "cluster": {
                "type": "string",
                "description": "Real cluster letter A-G, e.g. 'B' for deep-learning/foundation-model forecasts",
            },
            "time_format": {
                "type": "string",
                "description": "Real granularity to fetch, e.g. '1min'/'1H'/'1D'/'1W'. Defaults to '1D'.",
            },
        },
        "required": ["ticker", "cluster"],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import json

        import httpx

        from .angle_clusters import ANGLE_CLUSTERS

        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None

        ticker = kwargs["ticker"].strip().upper()
        cluster = str(kwargs["cluster"]).strip().upper()
        time_format = str(kwargs.get("time_format") or "1D").strip()

        members = ANGLE_CLUSTERS.get(cluster)
        if members is None:
            return json.dumps({
                "status": "error",
                "error": f"Unknown cluster {cluster!r}. Real clusters: {sorted(ANGLE_CLUSTERS)}",
            })

        base = self._services_config.get("vinu_initial_analysis", "http://localhost:8083").rstrip("/")
        url = f"{base}/analysis"
        v1_base = f"{base}/v1/stage1/vinu-initial-analysis"
        import os
        stage1 = os.getenv("VINU_STAGE1_START_DATE", "2022-01-01")
        time_range = f"{stage1}T00:00:00Z_2026-07-01T00:00:00Z"

        with httpx.Client(timeout=60.0, headers=_h) as client:
            results = _fetch_angle_results(
                client, url, v1_base, ticker, time_format, members, time_range, stage1,
            )

        with_data = sum(1 for r in results.values() if r.get("row_count", 0) > 0)
        return json.dumps({
            "ticker": ticker,
            "cluster": cluster,
            "cluster_members": members,
            "time_format": time_format,
            "angle_count": len(members),
            "angles_with_data": with_data,
            "angles": results,
        })


class ExplainAngleTool(BaseTool):
    """Genuinely on-demand, not an always-injected glossary block -- a
    specialist only pays the token cost when it calls this, for an angle
    it doesn't already recognize (real gap this closes:
    missing-pieces-of-system/angle-comprehension-hierarchy/00-explanation.md,
    section 1 -- angles.yaml has real title/purpose per angle, but nothing
    that reaches an LLM prompt ever read it before this)."""

    name = "explain_angle"
    description = (
        "Explain what a vinu-initial-analysis angle actually measures, how "
        "much to trust it, and any real gotcha (e.g. an angle whose "
        "model_backend is always a fallback proxy, never the real "
        "pretrained model) -- call this for any angle name from "
        "get_all_angles' response that isn't already clear from its name "
        "alone. Accepts one or more angle names at once."
    )
    parameters = {
        "type": "object",
        "properties": {
            "angle_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "One or more real angle ids, e.g. ['shock_personality', 'tips_regime_aware_transformer']",
            },
        },
        "required": ["angle_names"],
    }
    is_readonly = True

    def execute(self, **kwargs) -> str:
        import json

        from .angle_glossary import explain_angle

        angle_names = kwargs.get("angle_names") or []
        if isinstance(angle_names, str):
            angle_names = [angle_names]
        return json.dumps({name: explain_angle(str(name)) for name in angle_names})
