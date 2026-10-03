"""v1 B4 of the-inconsistencies-v2 (plan item 2.4e, refinement slice).

The refinement prompt showed the LLM five scalars of the ~35-field metric row
its candidate is ranked and judged on. With `refine_prompt_full_metrics_enabled`
the rest of the headline row (Sortino, Calmar, CVaR 95, profit factor, win/loss
ratio, turnover, Sharpe CI + p-value) is shown too. Off by default; off is
byte-identical to before.

Deliberately NOT done (need new fetches or a policy call; see
implementation-status.md): maturity tier, synthesis, eval catalog, drawdown
events and correlation note in the generation story.
"""

from __future__ import annotations

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.llm_generator import LlmStrategyGenerator, _build_refinement_prompt
from vinu_research.models import BacktestMetrics, BacktestResult, CriticFeedback

_CODE = "class UserStrategy:\n    def generate_weights(self, data):\n        return data\n"


def _result() -> BacktestResult:
    return BacktestResult(
        run_id="r1", strategy_name="UserStrategy",
        metrics=BacktestMetrics(
            sharpe_ratio=1.1, max_drawdown=-0.12, win_rate=0.55, total_return=0.2,
            sortino_ratio=1.7, calmar_ratio=0.9, cvar_95=-0.031, profit_factor=1.4,
            win_loss_ratio=1.2, annual_turnover=3.5,
            sharpe_ci_95_low=0.2, sharpe_ci_95_high=2.0, sharpe_p_value=0.041,
        ),
        benchmark_metrics={}, trade_count=42, equity_points=100,
    )


def _critique() -> CriticFeedback:
    return CriticFeedback(verdict="REFINE", reasoning="too few trades", suggestions=["trade more"])


def _prompt(**kw) -> str:
    return _build_refinement_prompt(
        "SMA crossover", "AAPL", "2024-01-01", "2024-12-31", _CODE, _result(), _critique(), **kw,
    )


# ------------------------------------------------------------------ the builder

def test_off_is_byte_identical_and_has_only_the_five_scalars():
    assert _prompt() == _prompt(full_metrics=False)
    out = _prompt()
    for field in ("Sharpe:", "MaxDD:", "Win Rate:", "Total Return:", "Trade Count:"):
        assert field in out
    for extra in ("Sortino", "Calmar", "CVaR", "Profit Factor", "Turnover", "95% CI"):
        assert extra not in out


def test_on_adds_the_rest_of_the_row_with_the_real_numbers():
    out = _prompt(full_metrics=True)
    assert "- Sortino: 1.70" in out and "- Calmar: 0.90" in out
    assert "- CVaR 95 (daily): -3.10%" in out
    assert "- Profit Factor: 1.40" in out and "- Win/Loss Ratio: 1.20" in out
    assert "- Annual Turnover: 3.50" in out
    assert "- Sharpe 95% CI: [0.20, 2.00] (p=0.041)" in out


def test_on_keeps_the_extra_lines_inside_the_backtest_block_before_the_critic():
    out = _prompt(full_metrics=True)
    assert out.index("Backtest results") < out.index("- Trade Count: 42") < out.index("- Sortino") < out.index("Critic verdict")


def test_on_leaves_everything_else_unchanged():
    on = _prompt(full_metrics=True).splitlines()
    off = _prompt().splitlines()
    assert [l for l in on if l not in off and not l.startswith("- ")] == []  # only metric bullet lines were added
    assert [l for l in off if l not in on] == []


# ------------------------------------------------------------------ the generator path

class _Capture:
    def __init__(self):
        self.prompts: list[str] = []

    def is_configured(self) -> bool:
        return True

    async def chat_json(self, system: str, user: str):
        self.prompts.append(user)
        return None  # no candidate is needed -- only the prompt is under test


async def _refine(story):
    llm = _Capture()
    await LlmStrategyGenerator(llm).refine(
        user_idea="SMA crossover", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31",
        previous_code=_CODE, last_result=_result(), last_critique=_critique(), story=story,
    )
    return llm.prompts[0]


@pytest.mark.asyncio
async def test_story_flag_reaches_the_prompt():
    assert "Sortino" in await _refine({"full_metrics": True})


@pytest.mark.asyncio
async def test_no_story_or_flag_false_leaves_the_prompt_unchanged():
    assert "Sortino" not in await _refine(None)
    assert "Sortino" not in await _refine({"full_metrics": False})
    assert "Sortino" not in await _refine({"memory_context": "x"})


# ------------------------------------------------------------------ config

def test_config_flag_defaults_off_and_reads_the_env(monkeypatch):
    from vinu_research.config import load_config

    assert ResearchConfig().refine_prompt_full_metrics_enabled is False
    monkeypatch.setenv("VINU_RESEARCH_REFINE_PROMPT_FULL_METRICS_ENABLED", "true")
    assert load_config().refine_prompt_full_metrics_enabled is True
    monkeypatch.setenv("VINU_RESEARCH_REFINE_PROMPT_FULL_METRICS_ENABLED", "no")
    assert load_config().refine_prompt_full_metrics_enabled is False


# ------------------------------------------------------------------ the loop wires the flag into the story

class _Configured:
    def is_configured(self) -> bool:
        return True


async def _loop_refine_story(monkeypatch, enabled: bool):
    from unittest.mock import AsyncMock

    import vinu_research.loop as loop_module
    from vinu_research.models import LlmCandidate

    calls: list[dict] = []

    class _FakeGenerator:
        def __init__(self, llm_client):
            pass

        async def refine(self, **kwargs):
            calls.append(kwargs)
            return [LlmCandidate(code="class UserStrategy: REFINED", validated=True)]

    monkeypatch.setattr(loop_module, "LlmStrategyGenerator", _FakeGenerator)
    loop = loop_module.StrategyResearchLoop(
        config=ResearchConfig(generator_mode="llm", refine_prompt_full_metrics_enabled=enabled),
    )
    loop._llm = _Configured()
    loop._symbol, loop._from_date, loop._to_date = "AAPL", "2024-01-01", "2024-12-31"
    monkeypatch.setattr(loop, "_run_backtest", AsyncMock(return_value=None))
    await loop._default_quant_coder(
        "SMA crossover", 2, _result(), _critique(), previous_code="class UserStrategy: PREVIOUS",
    )
    return calls[0]["story"]


@pytest.mark.asyncio
async def test_loop_marks_the_story_when_the_flag_is_on(monkeypatch):
    story = await _loop_refine_story(monkeypatch, True)
    assert story is not None and story.get("full_metrics") is True


@pytest.mark.asyncio
async def test_loop_leaves_the_story_unmarked_when_the_flag_is_off(monkeypatch):
    story = await _loop_refine_story(monkeypatch, False)
    assert not (story or {}).get("full_metrics")
