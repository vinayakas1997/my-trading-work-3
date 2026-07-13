"""HTTP routes for feature catalog."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException

from vinu_features.compute.feature_catalog import format_help, get_indicator, indicator_meta_to_dict, list_indicators
from vinu_features.server.schemas import FeatureCatalogResponse, IndicatorMetaOut

router = APIRouter(tags=["catalog"])


@router.get("/features", response_model=FeatureCatalogResponse)
def list_features() -> FeatureCatalogResponse:
    data = [IndicatorMetaOut(**indicator_meta_to_dict(m)) for m in list_indicators()]
    return FeatureCatalogResponse(count=len(data), data=data)


@router.get("/features/{symbol_or_kind}")
def get_feature_or_symbol(symbol_or_kind: str, indicators: str | None = None) -> Any:
    from vinu_features.compute.feature_catalog import list_indicators, get_indicator, format_help
    from vinu_features.server.routes_requests import get_service
    from fastapi import HTTPException
    import httpx
    
    known_kinds = {m.kind.lower() for m in list_indicators()}
    # Also support parsing kinds with parameters like rsi_14, sma_20
    is_known = False
    for k in known_kinds:
        if symbol_or_kind.lower() == k or symbol_or_kind.lower().startswith(k + "_"):
            is_known = True
            break
            
    if is_known:
        # Treat as kind
        try:
            meta = get_indicator(symbol_or_kind)
        except ValueError as exc:
            # Try parsing prefix for parametrized names
            parts = symbol_or_kind.split("_")
            if len(parts) > 1:
                prefix = parts[0]
                try:
                    meta = get_indicator(prefix)
                except ValueError:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
            else:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        out = IndicatorMetaOut(**indicator_meta_to_dict(meta))
        out.help_text = format_help(symbol_or_kind)
        return out
    else:
        # Treat as ticker symbol!
        svc = get_service()
        url = f"{svc.config.stock_api_url.rstrip('/')}/candles/{symbol_or_kind.upper()}"
        params = {"days": 60}  # get enough history to compute indicators
        if indicators:
            params["indicators"] = indicators
        try:
            resp = httpx.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            candles = data.get("data", [])
            if not candles:
                return {"symbol": symbol_or_kind, "values": {}, "signal": 0.0}
            
            # Get the latest candle
            latest = candles[-1]
            
            # Extract indicators
            ind_names = [i.strip().lower() for i in indicators.split(",")] if indicators else []
            values = {}
            for name in ind_names:
                values[name] = latest.get(name, 0.0)
            
            signal = latest.get("signal", 0.0)
            return {
                "symbol": symbol_or_kind,
                "values": values,
                "signal": signal
            }
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Failed to fetch features from stock-api: %s", exc)
            return {"symbol": symbol_or_kind, "values": {}, "signal": 0.0}

