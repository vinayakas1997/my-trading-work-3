"""Load ticker_news.yaml provider config."""

from __future__ import annotations

from pathlib import Path

import yaml

from vinu_news.providers.base import TickerNewsProviderConfig

_CONFIG_PATH = Path(__file__).resolve().parent / "ticker_news.yaml"


def load_ticker_news_providers(path: Path | None = None) -> list[TickerNewsProviderConfig]:
    cfg_path = path or _CONFIG_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    items = raw.get("providers") or []
    configs: list[TickerNewsProviderConfig] = []
    for item in items:
        configs.append(
            TickerNewsProviderConfig(
                id=str(item["id"]),
                enabled=bool(item.get("enabled", True)),
                priority=int(item.get("priority", 100)),
            )
        )
    return sorted(configs, key=lambda c: c.priority)


def set_provider_enabled(
    provider_id: str, enabled: bool, path: Path | None = None
) -> TickerNewsProviderConfig:
    """Toggle a ticker-news provider's enabled flag in ticker_news.yaml."""
    cfg_path = path or _CONFIG_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    items = raw.get("providers") or []

    match = next((item for item in items if str(item["id"]) == provider_id), None)
    if match is None:
        raise ValueError(f"Provider not found: {provider_id}")
    match["enabled"] = enabled

    cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return TickerNewsProviderConfig(
        id=str(match["id"]),
        enabled=bool(match.get("enabled", True)),
        priority=int(match.get("priority", 100)),
    )
