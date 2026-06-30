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
from vinu_stock.providers.yahoo import YahooProvider

ProviderRole = Literal["backfill", "live", "fallback"]

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "providers.yaml"


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
