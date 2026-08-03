"""Freshness Contract — reader side. The recompute trigger
(`vinu-research`'s `regime_recompute_scan()`) keeps regime/correlation data
from going stale in the background; this is the other half — something that
checks a value's age at the point the agent is about to use it and labels it
`STALE` if the scheduled recompute hasn't run recently enough. Neither side
implies the other: a working recompute job doesn't help if nothing ever
checks whether it actually ran on time for a given symbol.

Reads `analysis_at` off `vinu-initial-analysis`'s existing angle rows
(`GET /analysis/angle/{angle_name}/{ticker}`) — no new field needed there,
every `regime_analysis` row already stamps this on write
(`angles/regime_analysis/compute.py`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

STALE_AFTER_DAYS = 2.0
_DEFAULT_ANGLE = "regime_analysis"


def _parse_iso(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


class FreshnessChecker:
    def __init__(
        self,
        services_config: dict | None = None,
        stale_after_days: float = STALE_AFTER_DAYS,
    ) -> None:
        self._services_config = services_config or {}
        self._stale_after_days = stale_after_days

    def check_symbols(
        self, symbols: list[str], angle: str = _DEFAULT_ANGLE
    ) -> list[dict[str, Any]]:
        """Best-effort: any per-symbol fetch failure is skipped, not raised.
        Returns one finding per symbol whose latest `analysis_at` is older
        than the staleness threshold. Symbols with no rows at all (angle
        never computed) are skipped — that's a different failure mode
        ("no_data"/"insufficient_data", already surfaced elsewhere), not a
        freshness one."""
        base_url = self._services_config.get("vinu_initial_analysis")
        if not base_url:
            return []

        findings: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        import httpx

        for symbol in sorted(set(s for s in symbols if s)):
            try:
                resp = httpx.get(
                    f"{base_url}/analysis/angle/{angle}/{symbol}", timeout=5.0,
                )
                if resp.status_code != 200:
                    continue
                payload = resp.json()
            except Exception:
                logger.debug("FreshnessChecker: fetch failed for %s", symbol, exc_info=True)
                continue

            rows = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(rows, list) or not rows:
                continue

            latest: datetime | None = None
            for row in rows:
                if not isinstance(row, dict):
                    continue
                parsed = _parse_iso(row.get("analysis_at", ""))
                if parsed is not None and (latest is None or parsed > latest):
                    latest = parsed

            if latest is None:
                continue

            age_days = (now - latest).total_seconds() / 86400.0
            if age_days > self._stale_after_days:
                findings.append({
                    "symbol": symbol,
                    "angle": angle,
                    "analysis_at": latest.isoformat(),
                    "age_days": round(age_days, 1),
                })

        return findings
