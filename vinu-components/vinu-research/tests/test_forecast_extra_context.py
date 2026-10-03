"""v1 B3 of the-inconsistencies-v2 (plan item 2.4e, forecast slice).

The forecast LLM never saw the current market regime or the options-implied
move, although the Trade Score and the size multipliers apply both seconds
later -- so a forecast that ignored them was then scaled against them. With
`forecast_prompt_extra_context_enabled` on, both are shown to the forecast
prompt. Off by default; with it off the prompt is byte-identical to before.

Deliberately NOT done here (each needs a new data fetch inside authoring, or a
policy call, so it is recorded in implementation-status.md instead): synthesis
brief, evidence brief, evaluation-catalog line, drawdown events, correlation note.
"""

from __future__ import annotations

import pandas as pd
import pytest

from vinu_research.config import ResearchConfig
from vinu_research.forecast_skill import _build_forecast_prompt, generate_forecast
from vinu_research.trade_plan_authoring import author_trade_plan

pytestmark = pytest.mark.asyncio


# ------------------------------------------------------------------ the prompt builder (pure)

def _prompt(**kw) -> str:
    return _build_forecast_prompt("AAPL", {"a": 1}, {"b": 2}, **kw)


async def test_no_extra_context_is_byte_identical_to_the_old_prompt():
    assert _prompt() == _prompt(extra_context=None) == _prompt(extra_context={})
    assert "Market Context" not in _prompt()


async def test_regime_is_rendered_when_given():
    out = _prompt(extra_context={"current_regime": "bull", "options": None})
    assert "=== Market Context ===" in out and "current market regime: bull" in out
    assert "options-implied:" not in out
    assert "already use this regime," in out  # the note names only what is actually shown


async def test_options_are_rendered_only_when_the_snapshot_is_ok():
    ok = _prompt(extra_context={"current_regime": None, "options": {
        "status": "ok", "atm_iv": 0.32, "days_to_nearest_expiry": 21}})
    assert "options-implied: atm_iv=0.32, days_to_nearest_expiry=21" in ok
    bad = _prompt(extra_context={"current_regime": None, "options": {"status": "unavailable", "atm_iv": 0.32}})
    assert "Market Context" not in bad and "atm_iv" not in bad


@pytest.mark.parametrize("ctx", [
    {"current_regime": None, "options": None},
    {"current_regime": "   ", "options": None},
    {"current_regime": 7, "options": "junk"},
])
async def test_nothing_usable_renders_no_section_at_all(ctx):
    assert "Market Context" not in _prompt(extra_context=ctx)


async def test_section_sits_after_maturity_and_before_the_ticker_summary():
    out = _build_forecast_prompt(
        "AAPL", {}, {},
        summary_context={"summary": "SUMMARY-TEXT"},
        maturity_context={"tier": "early_live"},
        extra_context={"current_regime": "bear"},
    )
    assert out.index("=== System Maturity ===") < out.index("=== Market Context ===") < out.index("SUMMARY-TEXT")


# ------------------------------------------------------------------ generate_forecast passes it through

class _CapturingLlm:
    def __init__(self):
        self.prompts: list[str] = []

    async def chat_json(self, system, user, *, raise_on_failure=False):
        self.prompts.append(user)
        return {"direction": "long", "confidence": 0.7, "magnitude_pct": 0.03,
                "magnitude_std": 0.01, "horizon_days": 3, "reasoning": "x"}


async def test_generate_forecast_forwards_extra_context_to_the_prompt():
    llm = _CapturingLlm()
    await generate_forecast("AAPL", {}, {}, ResearchConfig(), llm, extra_context={"current_regime": "high_vol"})
    assert "current market regime: high_vol" in llm.prompts[0]
    await generate_forecast("AAPL", {}, {}, ResearchConfig(), llm)
    assert "Market Context" not in llm.prompts[1]


# ------------------------------------------------------------------ through author_trade_plan

class _Tools:
    def __init__(self, regime="bull", regime_raises=False):
        self.regime = regime
        self.regime_raises = regime_raises
        self.regime_reads = 0

    async def get_benchmark_data(self, symbol, from_date, to_date):
        return pd.Series(([0.01] * 65 + [-0.005] * 35))

    async def get_angle_rows(self, angle_name, symbol):
        if angle_name == "regime_analysis":
            self.regime_reads += 1
            if self.regime_raises:
                raise ConnectionError("angle service down")
            return [{"metric": "current_regime", "regime": self.regime}] if self.regime else []
        return []

    async def get_options_snapshot(self, symbol):
        return None

    async def get_latest_debate_run(self, preset_name, symbol):
        return None

    async def fetch_screener_rank_percentile(self, ranker_id, symbol):
        return None


def _config(enabled: bool) -> ResearchConfig:
    return ResearchConfig(forecast_prompt_extra_context_enabled=enabled)


async def test_flag_defaults_to_off():
    assert ResearchConfig().forecast_prompt_extra_context_enabled is False


async def test_flag_off_the_forecast_prompt_has_no_market_context():
    llm = _CapturingLlm()
    await author_trade_plan("AAPL", "daily", _config(False), _Tools("bull"), llm)
    assert "Market Context" not in llm.prompts[0]


async def test_flag_on_the_forecast_prompt_carries_the_regime():
    llm = _CapturingLlm()
    await author_trade_plan("AAPL", "daily", _config(True), _Tools("bear"), llm)
    assert "current market regime: bear" in llm.prompts[0]


async def test_flag_on_does_not_fetch_the_regime_a_second_time():
    off, on = _Tools("bull"), _Tools("bull")
    await author_trade_plan("AAPL", "daily", _config(False), off, _CapturingLlm())
    await author_trade_plan("AAPL", "daily", _config(True), on, _CapturingLlm())
    assert on.regime_reads == off.regime_reads  # the pre-forecast fetch is reused for sizing


async def test_flag_on_a_regime_fetch_failure_still_produces_a_plan_without_the_line():
    llm = _CapturingLlm()
    plan = await author_trade_plan("AAPL", "daily", _config(True), _Tools(regime_raises=True), llm)
    assert plan is not None and "Market Context" not in llm.prompts[0]
    assert any("regime=unknown" in r for r in plan.trade_score.reasons)


async def test_flag_on_no_regime_row_renders_no_section():
    llm = _CapturingLlm()
    await author_trade_plan("AAPL", "daily", _config(True), _Tools(regime=None), llm)
    assert "Market Context" not in llm.prompts[0]


async def test_flag_does_not_change_the_plan_when_the_context_is_empty():
    a = await author_trade_plan("AAPL", "daily", _config(False), _Tools(regime=None), _CapturingLlm())
    b = await author_trade_plan("AAPL", "daily", _config(True), _Tools(regime=None), _CapturingLlm())
    assert (a.direction, a.risk_bands.max_position_size_pct) == (b.direction, b.risk_bands.max_position_size_pct)
