from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vinu_research.shadow.models import ShadowProfile

LOG = logging.getLogger(__name__)


def select_liquid_baskets(
    profile: ShadowProfile,
    max_symbols: int = 20,
) -> list[str]:
    seen: set[str] = set()
    symbols: list[str] = []
    for market in profile.preferred_markets:
        m = market.strip().upper()
        if m and m not in seen:
            seen.add(m)
            symbols.append(m)
    return symbols[:max_symbols]


def prepare_backtest_config(
    profile: ShadowProfile,
    start_date: str,
    end_date: str,
    output_dir: str | Path | None = None,
) -> str:
    symbols = select_liquid_baskets(profile)
    run_dir = Path(output_dir or Path.home() / ".vinu" / "shadow" / profile.shadow_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "run_id": f"shadow_{profile.shadow_id}",
        "shadow_id": profile.shadow_id,
        "symbols": symbols,
        "start_date": start_date,
        "end_date": end_date,
        "interval": "1d",
        "initial_capital": 100_000.0,
        "transaction_cost_pct": 0.001,
        "slippage_pct": 0.0005,
        "allow_short": True,
        "rules": [r.to_dict() for r in profile.rules],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    return str(config_path)


def parse_backtest_results(run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir)
    run_card_path = run_path / "run_card.json"
    if run_card_path.exists():
        try:
            return json.loads(run_card_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            LOG.warning("Failed to parse run card at %s: %s", run_card_path, exc)
    return {}
