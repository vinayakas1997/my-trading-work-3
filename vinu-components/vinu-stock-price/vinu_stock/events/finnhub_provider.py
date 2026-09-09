"""Finnhub calendar provider (free tier: 60 req/min).

Two endpoints:
  GET /calendar/earnings?from&to&symbol   -> {"earningsCalendar": [...]}
  GET /calendar/economic?from&to          -> {"economicCalendar": [...]}

Free-tier key. On any HTTP problem the methods return [] and log -- the caller
(events.poller) then keeps whatever rows are already in the store, so a bad
pull degrades to "yesterday's calendar", never to an empty one.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from vinu_stock.events.store import MACRO_SYMBOL, EventRecord
from vinu_stock.providers.config.settings import REQUEST_TIMEOUT_SEC
from vinu_infra.retry import http_get_with_retry

LOG = logging.getLogger(__name__)

_BASE = "https://finnhub.io/api/v1"

# Finnhub earnings `hour` codes -> a UTC hour to stamp the event at, so a
# blackout window has something finer than "that day" to work with. ET market
# hours; the blackout window is measured in whole hours so this need not be
# exact.
_HOUR_MAP = {"bmo": 13.5, "amc": 20.0, "dmh": 16.75}
_DEFAULT_HOUR = 16.0  # midday ET-ish when Finnhub gives no hour

# Macro events we actually gate on (US, high-impact, scheduled). Matched
# case-insensitively as substrings of Finnhub's `event` string.
_MACRO_KEYWORDS = (
    "fomc", "federal funds", "interest rate decision", "rate decision",
    "cpi", "consumer price index",
    "nonfarm", "non-farm", "nfp", "employment situation",
    "pce", "personal consumption expenditure",
    "gdp",
)


def _iso_day(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d")


def _day_plus_hour_to_ts(day: str, hour: float) -> float:
    try:
        base = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return 0.0
    return base.timestamp() + hour * 3600.0


class FinnhubCalendarProvider:
    provider_id = "finnhub"

    def __init__(self, api_key: str | None) -> None:
        self._key = (api_key or "").strip()

    def is_configured(self) -> bool:
        return bool(self._key)

    def _get(self, path: str, params: dict[str, str]) -> dict | None:
        params = {**params, "token": self._key}
        try:
            resp = http_get_with_retry(
                f"{_BASE}{path}", params=params, timeout=REQUEST_TIMEOUT_SEC
            )
            if getattr(resp, "status_code", 200) != 200:
                LOG.warning("Finnhub %s -> HTTP %s", path, resp.status_code)
                return None
            return resp.json() or {}
        except Exception as exc:  # noqa: BLE001 -- best-effort read; caller keeps old rows
            LOG.warning("Finnhub %s failed: %s", path, exc)
            return None

    def get_earnings(
        self, symbols: list[str], from_epoch: float, to_epoch: float
    ) -> list[EventRecord]:
        if not self.is_configured():
            return []
        frm, to = _iso_day(from_epoch), _iso_day(to_epoch)
        out: list[EventRecord] = []
        for raw in symbols:
            sym = raw.strip().upper()
            if not sym:
                continue
            data = self._get("/calendar/earnings", {"from": frm, "to": to, "symbol": sym})
            if not data:
                continue
            for row in data.get("earningsCalendar") or []:
                day = str(row.get("date") or "")
                if not day:
                    continue
                hour = _HOUR_MAP.get(str(row.get("hour") or "").lower(), _DEFAULT_HOUR)
                ts = _day_plus_hour_to_ts(day, hour)
                if ts <= 0.0:
                    continue
                out.append(
                    EventRecord(
                        symbol=sym, kind="earnings", event_ts=ts,
                        title=f"{sym} earnings ({row.get('hour') or 'time TBD'})",
                        severity=2,
                    )
                )
        return out

    def get_economic(self, from_epoch: float, to_epoch: float) -> list[EventRecord]:
        if not self.is_configured():
            return []
        frm, to = _iso_day(from_epoch), _iso_day(to_epoch)
        data = self._get("/calendar/economic", {"from": frm, "to": to})
        if not data:
            return []
        out: list[EventRecord] = []
        for row in data.get("economicCalendar") or []:
            country = str(row.get("country") or "").upper()
            if country not in ("US", "USA", "UNITED STATES"):
                continue
            event = str(row.get("event") or "")
            if not any(k in event.lower() for k in _MACRO_KEYWORDS):
                continue
            # Finnhub `time` is "YYYY-MM-DD HH:MM:SS" (UTC) or just the date.
            raw_time = str(row.get("time") or "")
            ts = 0.0
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    ts = datetime.strptime(raw_time, fmt).replace(tzinfo=timezone.utc).timestamp()
                    break
                except (TypeError, ValueError):
                    continue
            if ts <= 0.0:
                continue
            impact = str(row.get("impact") or "").lower()
            out.append(
                EventRecord(
                    symbol=MACRO_SYMBOL, kind="economic", event_ts=ts,
                    title=f"US macro: {event}",
                    severity=2 if impact in ("high", "3") else 1,
                )
            )
        return out
