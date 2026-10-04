"""features-logic-checking: the daily allocation worked out by hand.

Two strategies with equal volatility start at 0.5 / 0.5. The market regime is bull.
  A is tagged `trending` (a bull regime favours it): regime multiplier 1 + 0.3 = 1.3
     and its outcome accuracy is 0.8:                 outcome multiplier 1 + 0.3 * (2 * 0.8 - 1) = 1.18
  B is tagged `ranging` (not favoured):               regime multiplier 1 - 0.3 = 0.7, outcome untracked: 1.0
Tilted: A = 0.5 * 1.3 * 1.18 = 0.767, B = 0.5 * 0.7 * 1.0 = 0.35 -> renormalised: A = 0.767 / 1.117 = 0.6867,
B = 0.3133.
Capital: equity 100,000, reserve 10%, drawdown status `ok` (x1.0), maturity gating off (x1.0)
  -> deployable = 100,000 * 0.9 = 90,000.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from vinu_portfolio.config import PortfolioConfig
from vinu_portfolio.service import PortfolioService


def _service(tmp_path, tags: str) -> PortfolioService:
    tags_file = tmp_path / "tags.yaml"
    tags_file.write_text(tags, encoding="utf-8")
    svc = PortfolioService(config=PortfolioConfig(
        tags_path=tags_file, regime_tilt_bound=0.3, outcome_tilt_bound=0.3, confidence_tilt_bound=0.0,
        max_per_strategy_weight=1.0, reserve_fraction=0.1, data_root=tmp_path / "data",
    ))
    dates = pd.date_range("2026-06-01", periods=60)
    up_down = [0.01, -0.01] * 30
    svc.list_active_strategies = AsyncMock(return_value=[
        {"name": "strat_a", "kind": "yaml", "symbol": "AAPL"},
        {"name": "strat_b", "kind": "yaml", "symbol": "MSFT"},
    ])
    svc._build_returns_df = AsyncMock(return_value=pd.DataFrame(
        {"strat_a": up_down, "strat_b": [-x for x in up_down]}, index=dates,
    ))
    svc._fetch_benchmark_regime = AsyncMock(return_value={"status": "ok", "regime": "bull"})

    async def confidence(strategy):
        if strategy.get("name") == "strat_a":
            return {"source": "calibration", "accuracy": 0.8, "n_entries": 20}
        return {"source": "not_tracked", "accuracy": None, "n_entries": 0}

    svc._fetch_outcome_confidence = confidence
    svc._fetch_account_equity = AsyncMock(return_value=100_000.0)
    svc._fetch_positions = AsyncMock(return_value=[])
    return svc


TAGS = "strategies:\n  strat_a:\n    regime: [trending]\n  strat_b:\n    regime: [ranging]\n"


def test_the_tilts_and_the_deployable_capital_match_the_hand_calculation(tmp_path):
    out = asyncio.run(_service(tmp_path, TAGS).compute_daily_allocation())
    by = {w["name"]: w for w in out["weights"]}
    assert by["strat_a"]["base_weight"] == pytest.approx(0.5, abs=0.01)
    assert by["strat_a"]["regime_multiplier"] == pytest.approx(1.3)
    assert by["strat_b"]["regime_multiplier"] == pytest.approx(0.7)
    assert by["strat_a"]["outcome_multiplier"] == pytest.approx(1.18)
    assert by["strat_b"]["outcome_multiplier"] == pytest.approx(1.0)
    assert by["strat_a"]["target_weight"] == pytest.approx(0.6867, abs=0.005)
    assert by["strat_b"]["target_weight"] == pytest.approx(0.3133, abs=0.005)
    assert sum(w["target_weight"] for w in out["weights"]) == pytest.approx(1.0, abs=0.001)
    assert out["account_equity"] == 100_000.0 and out["deployable_equity"] == pytest.approx(90_000.0)


def test_without_the_tags_file_the_regime_tilt_is_silently_neutral(tmp_path):
    """The F5 deployment fault in miniature: when the tags file is missing, every regime multiplier is 1.0 and the
    sleeves read `untagged` -- the system works, but the regime has no effect on allocation."""
    svc = _service(tmp_path, TAGS)
    svc._config.tags_path = tmp_path / "does-not-exist.yaml"
    out = asyncio.run(svc.compute_daily_allocation())
    assert {w["regime_multiplier"] for w in out["weights"]} == {1.0}
    assert set(out["sleeves"]) == {"untagged"}


# ---- the base weights and the concentration cap, by hand

def _two_strategy_service(tmp_path, **cfg) -> PortfolioService:
    import numpy as np

    svc = PortfolioService(config=PortfolioConfig(max_per_strategy_weight=1.0, data_root=tmp_path / "data", **cfg))
    dates = pd.date_range("2026-06-01", periods=60)
    base = np.array([1.0, -1.0] * 30)
    svc.list_active_strategies = AsyncMock(return_value=[
        {"name": "calm", "kind": "yaml", "symbol": "AAPL"}, {"name": "wild", "kind": "yaml", "symbol": "MSFT"},
    ])
    # calm's daily volatility is half of wild's: sigma_calm = s, sigma_wild = 2s
    svc._build_returns_df = AsyncMock(return_value=pd.DataFrame(
        {"calm": 0.01 * base, "wild": 0.02 * np.roll(base, 1)}, index=dates,
    ))
    return svc


def _weights(svc) -> dict[str, float]:
    return {x["name"]: x["target_weight"] for x in asyncio.run(svc.build_portfolio())["weights"]}


def test_inverse_volatility_mode_gives_the_calmer_strategy_twice_the_weight(tmp_path):
    """Mode `inverse_vol`: weight proportional to 1/sigma -> 1/s : 1/(2s) = 2 : 1 -> calm 2/3 = 0.6667, wild 1/3."""
    w = _weights(_two_strategy_service(tmp_path, allocation_mode="inverse_vol"))
    assert w["calm"] == pytest.approx(2 / 3, abs=0.005) and w["wild"] == pytest.approx(1 / 3, abs=0.005)


def test_the_default_mode_is_hierarchical_risk_parity_which_for_two_assets_is_inverse_variance(tmp_path):
    """The default `allocation_mode` is `hrp`, not `inverse_vol` (the docstring of allocate_risk_parity and several docs
    still say inverse-vol). For two assets HRP splits by inverse VARIANCE: calm = sigma_wild^2 / (sigma_calm^2 +
    sigma_wild^2) = 4 / 5 = 0.8, wild 0.2 -- a stronger tilt to the calmer strategy than inverse-vol's 2/3."""
    assert PortfolioConfig().allocation_mode == "hrp"
    w = _weights(_two_strategy_service(tmp_path))
    assert w["calm"] == pytest.approx(0.8, abs=0.005) and w["wild"] == pytest.approx(0.2, abs=0.005)


def test_the_concentration_cap_is_enforced_and_the_excess_is_redistributed():
    """Weights 0.6 / 0.3 / 0.1 with a 0.4 cap: A is cut to 0.4 and its 0.2 excess goes to B and C in the ratio 3:1
    (B 0.45, C 0.15). B now exceeds the cap too: B is cut to 0.4, its 0.05 goes to C -> 0.4 / 0.4 / 0.2."""
    from vinu_portfolio.service import cap_concentration

    out = cap_concentration({"a": 0.6, "b": 0.3, "c": 0.1}, 0.4)
    assert out["a"] == pytest.approx(0.4) and out["b"] == pytest.approx(0.4) and out["c"] == pytest.approx(0.2)
    assert sum(out.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("action,expected_deployable", [("ok", 90_000.0), ("halve", 45_000.0), ("flat", 0.0), ("halt", 0.0)])
def test_the_drawdown_status_scales_the_deployable_capital(tmp_path, action, expected_deployable):
    """equity 100,000 x (1 - reserve 0.10) x drawdown multiplier (ok 1.0, halve 0.5, flat 0.0, halt 0.0)."""
    svc = _service(tmp_path, TAGS)
    svc._drawdown_status_store.record(action, -0.12, False)
    out = asyncio.run(svc.compute_daily_allocation())
    assert out["deployable_equity"] == pytest.approx(expected_deployable)
    assert out["account_equity"] == 100_000.0               # the real total stays visible
    assert out["drawdown_status"]["action"] == action
    # the RELATIVE weights do not change: a uniform multiplier would be a no-op once renormalised, so the ladder acts on
    # capital, not on the weight fractions
    assert sum(w["target_weight"] for w in out["weights"]) == pytest.approx(1.0, abs=0.001)
