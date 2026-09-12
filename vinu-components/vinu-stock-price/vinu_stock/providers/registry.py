"""Provider registry with configurable priority and roles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from vinu_stock.config import VinuStockConfig, load_config
from vinu_stock.providers.alpaca import AlpacaProvider
from vinu_stock.providers.base import FetchBarsResult, PriceProvider
from vinu_stock.providers.polygon import PolygonProvider
from vinu_stock.providers.tushare import TushareProvider
from vinu_stock.providers.yahoo import YahooProvider
from vinu_stock.providers.yfinance import YFinanceProvider

ProviderRole = Literal["backfill", "live", "fallback"]

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "providers.yaml"

import os as _os


def _env_chain(default: list[str]) -> list[str]:
    raw = _os.environ.get("VINU_PROVIDER_ORDER", "")
    if raw.strip():
        return [p.strip() for p in raw.split(",") if p.strip()]
    return default


FALLBACK_CHAINS: dict[str, list[str]] = {
    "us_equity": _env_chain(["alpaca", "polygon", "tushare", "yahoo"]),
    "crypto": ["alpaca", "yahoo"],
    "a_share": ["yahoo"],
}

VALID_SOURCES: set[str] = {"alpaca", "polygon", "yahoo", "stooq", "eastmoney", "ccxt", "akshare", "tushare", "local"}


def resolve_loader(
    market: str,
    registry: ProviderRegistry | None = None,
) -> PriceProvider | None:
    chain = FALLBACK_CHAINS.get(market, FALLBACK_CHAINS.get("us_equity", []))
    providers = registry._providers if registry else {}
    for provider_id in chain:
        provider = providers.get(provider_id)
        if provider is not None and provider.is_configured():
            return provider
    return None


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    enabled: bool
    priority: int
    roles: tuple[ProviderRole, ...]


def load_provider_configs(path: Path | None = None) -> list[ProviderConfig]:
    cfg_path = path or _CONFIG_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    items = raw.get("providers") or []
    configs: list[ProviderConfig] = []
    for item in items:
        roles = tuple(item.get("roles") or [])
        configs.append(
            ProviderConfig(
                id=str(item["id"]),
                enabled=bool(item.get("enabled", True)),
                priority=int(item.get("priority", 100)),
                roles=roles,  # type: ignore[arg-type]
            )
        )
    return sorted(configs, key=lambda c: c.priority)


class ProviderRegistry:
    def __init__(self, config: VinuStockConfig | None = None) -> None:
        self._config = config or load_config()
        self._configs = load_provider_configs()
        self._providers: dict[str, PriceProvider] = {
            "polygon": PolygonProvider(self._config),
            "alpaca": AlpacaProvider(self._config),
            "yahoo": YahooProvider(),
            "yfinance": YFinanceProvider(),
            "tushare": TushareProvider(),
        }

    def list_configs(self) -> list[ProviderConfig]:
        return list(self._configs)

    def provider_status(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for cfg in self._configs:
            provider = self._providers.get(cfg.id)
            out.append(
                {
                    "id": cfg.id,
                    "enabled": cfg.enabled,
                    "priority": cfg.priority,
                    "configured": provider.is_configured() if provider else False,
                }
            )
        return out

    def get(self, provider_id: str) -> PriceProvider | None:
        return self._providers.get(provider_id)

    def for_role(self, role: ProviderRole) -> list[PriceProvider]:
        out: list[PriceProvider] = []
        for cfg in self._configs:
            if not cfg.enabled or role not in cfg.roles:
                continue
            provider = self._providers.get(cfg.id)
            if provider is not None:
                out.append(provider)
        return out

    def fetch_bars_with_fallback(
        self,
        symbol: str,
        start_ts: int,
        end_ts: int,
        *,
        role: ProviderRole = "backfill",
    ) -> FetchBarsResult:
        errors: list[str] = []
        for provider in self.for_role(role):
            if not provider.is_configured() and provider.provider_id != "yahoo":
                errors.append(f"{provider.provider_id}: not configured")
                continue
            result = provider.fetch_bars(symbol, start_ts, end_ts)
            if result.success and result.bars:
                return result
            errors.append(f"{provider.provider_id}: {result.error or 'empty'}")
        if role != "fallback":
            for provider in self.for_role("fallback"):
                result = provider.fetch_bars(symbol, start_ts, end_ts)
                if result.success and result.bars:
                    return result
                errors.append(f"{provider.provider_id}: {result.error or 'empty'}")
        return FetchBarsResult(False, [], "; ".join(errors))

    def fetch_bars_multi_with_fallback(
        self,
        symbols: list[str],
        start_ts: int,
        end_ts: int,
        *,
        role: ProviderRole = "backfill",
    ) -> dict[str, FetchBarsResult]:
        """Batched equivalent of calling fetch_bars_with_fallback() once per
        symbol, with the same per-symbol provider fallback semantics.

        A provider that exposes fetch_bars_multi() (currently only
        AlpacaProvider) is asked for every symbol still unresolved in one
        call instead of one call each -- detected via hasattr(), the same
        duck-typed "optional batch capability" pattern vinu-screener's
        HttpStockDataSource.get_ohlcv_batch uses. Providers without it (or
        symbols they didn't return data for) fall through to one fetch_bars()
        call per remaining symbol, exactly like fetch_bars_with_fallback.
        """
        remaining = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
        results: dict[str, FetchBarsResult] = {}
        errors: dict[str, list[str]] = {s: [] for s in remaining}

        def _try_chain(chain_role: ProviderRole) -> None:
            nonlocal remaining
            for provider in self.for_role(chain_role):
                if not remaining:
                    return
                if not provider.is_configured() and provider.provider_id != "yahoo":
                    for s in remaining:
                        errors[s].append(f"{provider.provider_id}: not configured")
                    continue
                if hasattr(provider, "fetch_bars_multi"):
                    batch = provider.fetch_bars_multi(remaining, start_ts, end_ts)
                    still_missing = []
                    for s in remaining:
                        result = batch.get(s)
                        if result is not None and result.success and result.bars:
                            results[s] = result
                        else:
                            err = result.error if result is not None else "empty"
                            errors[s].append(f"{provider.provider_id}: {err or 'empty'}")
                            still_missing.append(s)
                    remaining = still_missing
                else:
                    still_missing = []
                    for s in remaining:
                        result = provider.fetch_bars(s, start_ts, end_ts)
                        if result.success and result.bars:
                            results[s] = result
                        else:
                            errors[s].append(f"{provider.provider_id}: {result.error or 'empty'}")
                            still_missing.append(s)
                    remaining = still_missing

        _try_chain(role)
        if remaining and role != "fallback":
            _try_chain("fallback")

        for s in remaining:
            results[s] = FetchBarsResult(False, [], "; ".join(errors[s]))
        return results

    def fetch_for_market(
        self,
        market: str,
        symbol: str,
        start_ts: int,
        end_ts: int,
    ) -> FetchBarsResult:
        chain = FALLBACK_CHAINS.get(market, FALLBACK_CHAINS.get("us_equity", []))
        errors: list[str] = []
        for provider_id in chain:
            provider = self._providers.get(provider_id)
            if provider is None:
                errors.append(f"{provider_id}: unknown")
                continue
            if not provider.is_configured() and provider_id != "yahoo":
                errors.append(f"{provider_id}: not configured")
                continue
            result = provider.fetch_bars(symbol, start_ts, end_ts)
            if result.success and result.bars:
                return result
            errors.append(f"{provider_id}: {result.error or 'empty'}")
        return FetchBarsResult(False, [], "; ".join(errors))
