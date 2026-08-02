"""Live options Greeks/IV tool — Alpaca option chain snapshot.

LIVE SNAPSHOT ONLY: Alpaca's `/v1beta1/options/snapshots` returns today's
quotes/greeks/IV with no historical lookup (historical option bars only
post-Feb-2024 anyway), so this is a present-time tool, deliberately NOT a
vinu-initial-analysis angle (which must answer questions over a historical
range this endpoint structurally cannot).
"""

import json
import logging
import os

import requests

from ..agent.tools import BaseTool

logger = logging.getLogger(__name__)

ALPACA_DATA_BASE_URL = os.environ.get("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets")
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.environ.get("ALPACA_API_SECRET", "")


def _auth_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        "Accept": "application/json",
    }


def _occ_strike(symbol: str) -> float | None:
    """AAPL YYMMDD C/O SSSSS -> strike (implied by the 5-digit scaling)."""
    if len(symbol) < 15:
        return None
    num = symbol[-8:]
    try:
        return float(int(num) / 1000.0)
    except (ValueError, TypeError):
        return None


def _occ_expiration(symbol: str) -> str | None:
    """AAPL YYMMDD C/O ... -> '20YY-MM-DD'."""
    if len(symbol) < 8:
        return None
    yy = symbol[4:6]
    mm = symbol[6:8]
    dd = symbol[8:10]
    try:
        return f"20{yy}-{mm}-{dd}"
    except Exception:
        return None


def _occ_type(symbol: str) -> str | None:
    return symbol[10:11] if len(symbol) >= 11 else None


def fetch_chain(symbol: str, limit: int = 60, expiration: str | None = None) -> list[dict[str, object]]:
    """Return a normalized list of contract rows with greeks + IV + quotes."""
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise ValueError("Alpaca API credentials not configured")
    params: dict[str, object] = {"limit": limit}
    if expiration:
        params["expiration_gte"] = expiration
        params["expiration_lte"] = expiration
    resp = requests.get(
        f"{ALPACA_DATA_BASE_URL}/v1beta1/options/snapshots/{symbol.upper()}",
        headers=_auth_headers(),
        params=params,
        timeout=20.0,
    )
    if resp.status_code == 401:
        raise PermissionError(
            "Options data returned HTTP 401 (credential/account lacks options-data entitlement)"
        )
    resp.raise_for_status()
    body = resp.json()
    snapshots = body.get("snapshots") or {}
    if not snapshots:
        return []

    rows: list[dict[str, object]] = []
    for contract_symbol, snap in snapshots.items():
        quote = snap.get("latestQuote") or {}
        greeks = snap.get("greeks")
        daily = snap.get("dailyBar") or {}
        iv = snap.get("impliedVolatility")
        bp = quote.get("bp")
        ap = quote.get("ap")
        mid = (bp + ap) / 2.0 if (bp is not None and ap is not None) else None
        row: dict[str, object] = {
            "contract_symbol": contract_symbol,
            "expiration": _occ_expiration(contract_symbol),
            "strike": _occ_strike(contract_symbol),
            "type": _occ_type(contract_symbol),
            "bid": bp,
            "ask": ap,
            "mid": round(mid, 4) if mid is not None else None,
            "last": (snap.get("latestTrade") or {}).get("p"),
            "volume": daily.get("v") if isinstance(daily, dict) else None,
            "implied_volatility": iv,
        }
        if iv is not None:
            row["iv_pct"] = round(float(iv) * 100.0, 2)
        if greeks:
            row.update({
                "delta": greeks.get("delta"),
                "gamma": greeks.get("gamma"),
                "theta": greeks.get("theta"),
                "vega": greeks.get("vega"),
                "rho": greeks.get("rho"),
            })
        rows.append(row)
    return rows


class OptionsGreeksTool(BaseTool):
    name = "get_options_greeks"
    description = (
        "Fetch live options chain data for a symbol: Greeks (delta, gamma, theta, vega, rho) and "
        "implied volatility, per contract. Live snapshot only (today's data, no historical lookup)."
    )
    parameters = {
        "symbol": {"type": "string", "description": "Underlying stock symbol (e.g., AAPL)"},
        "expiration": {
            "type": "string",
            "description": "Optional: filter to a single expiration date (YYYY-MM-DD)",
        },
        "limit": {
            "type": "integer",
            "description": "Max contracts to return (default 100)",
        },
    }
    is_readonly = True
    _as_of: str | None = None

    def execute(self, **kwargs) -> str:
        if self._as_of:
            return json.dumps({
                "status": "unavailable",
                "reason": "options Greeks/IV have no historical lookup; not available in replay mode",
            })
        symbol = str(kwargs.get("symbol", "")).upper()
        if not symbol:
            return json.dumps({"status": "error", "error": "symbol is required"})
        expiration = kwargs.get("expiration")
        limit = int(kwargs.get("limit", 100))
        try:
            rows = fetch_chain(symbol, limit=limit, expiration=expiration)
        except Exception as exc:
            logger.warning("Options fetch failed for %s: %s", symbol, exc)
            return json.dumps({"status": "error", "error": str(exc)})
        if not rows:
            return json.dumps({
                "status": "empty",
                "symbol": symbol,
                "message": "No options contracts returned (symbol has no listed options, or the market is closed).",
            })
        return json.dumps({
            "status": "ok",
            "symbol": symbol,
            "n_contracts": len(rows),
            "contracts": rows,
        }, indent=2)