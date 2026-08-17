"""Live-LLM smoke tests for prompt-dependent behavior (implementation-plan
task 08). Two behaviors that the fast suite only proves at the
deterministic/mocked layer are confirmed here against the REAL production
model:

  1. idea_generator's recipe-first preference (Phase 1): with a sweep
     recipe that genuinely covers the ask, the model should pick the
     recipe path; with a genuinely uncovered ask it should say "no recipe
     fits" and fall back to raw Python.
  2. angle_synthesizer's cross-angle consensus section (Phase 8): the
     model should report agree / diverge / insufficient_data verdicts
     that match the deterministic compare_angles results it was given.

This runs the REAL prompt (loaded from the live teams/ directory) and the
REAL model -- no mocks. The tool-call layer is already covered by the
deterministic unit tests; this suite confirms the model actually follows
the prompt's verdict/decision instructions.

EXCLUDED from the default run: set RUN_LIVE_LLM_TESTS=1 to run (real API
calls, real latency). If the configured model endpoint is unreachable the
tests skip with a clear reason rather than failing.

Actual model outputs are recorded (not just pass/fail) under
tests/live_llm_outputs/ -- read them, they are the reviewable evidence.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from vinu_agent.agent.angle_consensus import (
    compare_categorical,
    compare_directional,
)
from vinu_agent.agent.llm import create_llm_from_config
from vinu_agent.config import LLMConfig

RUN_LIVE = os.environ.get("RUN_LIVE_LLM_TESTS", "") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason="set RUN_LIVE_LLM_TESTS=1 to run live-LLM validation (real API calls and latency)",
)

BASE_URL = os.environ.get("VINU_LLM_BASE_URL", "http://localhost:8009/v1")
MODEL = os.environ.get("VINU_LLM_MODEL", "qwen36-35B")

OUTPUT_DIR = Path(__file__).parent / "live_llm_outputs"
TEAMS_DIR = Path(__file__).parent.parent / "teams"


def _require_live_model():
    """Pre-flight: skip cleanly (don't fail) when the model endpoint is
    unreachable, so `RUN_LIVE_LLM_TESTS=1` against a stopped stack skips
    instead of erroring."""
    import httpx

    try:
        httpx.get(BASE_URL.rstrip("/") + "/models", timeout=5).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"live LLM endpoint {BASE_URL} unreachable: {exc}")


def _llm():
    return create_llm_from_config(LLMConfig(
        provider="openai", model_name=MODEL, base_url=BASE_URL,
        timeout=300, context_window=32000,
    ))


def _record(name: str, scenario: str, user_prompt: str, output: str) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {scenario} ({time.strftime('%Y-%m-%d %H:%M:%S')})\n\n")
        f.write(f"MODEL: {MODEL} via {BASE_URL}\n\n")
        f.write("### USER PROMPT\n\n")
        f.write(user_prompt + "\n\n")
        f.write("### MODEL OUTPUT\n\n")
        f.write(output.strip() + "\n\n")
    return str(path)


def _chat(system: str, user: str) -> str:
    resp = _llm().chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    return resp.get("content", "")


def _agent_prompt(team: str, agent: str) -> str:
    from vinu_agent.agent.team import load_agent_spec

    return load_agent_spec(TEAMS_DIR / team / "agents" / agent).prompt


def _recipe_catalog() -> str:
    from vinu_research.generator import list_recipe_details

    lines = ["Available sweep recipes (key | name | tunable params):"]
    for d in list_recipe_details():
        lines.append(f"- {d['key']} | {d['name']} | {', '.join(d['params'].keys())}")
    return "\n".join(lines)


class TestIdeaGeneratorRecipeFirst:
    """The real prompt + the real model deciding between the recipe path
    and the raw-code exception path (task 08, item 1)."""

    def _run(self, scenario: str, task: str, angle_data: str) -> str:
        _require_live_model()
        system = _agent_prompt("research", "idea_generator")
        user = (
            "## Task\n"
            f"{task}\n\n"
            "## Real tool results (fetched for you)\n"
            f"{_recipe_catalog()}\n\n"
            f"### get_all_angles for the symbol\n{angle_data}\n\n"
            "Produce your final answer exactly as your instructions require "
            "(recipe output shape, or the raw-Python exception path with an "
            "explicit 'no recipe fits' statement)."
        )
        output = _chat(system, user)
        path = _record("idea_generator", scenario, user, output)
        return output, path

    def test_picks_recipe_when_one_covers_the_ask(self):
        output, path = self._run(
            "recipe-first: simple SMA-crossover tuning ask (a recipe covers it)",
            (
                "Generate a strategy idea for AAPL from 2023-01-01 to 2023-12-31: "
                "a fast/slow simple-moving-average crossover -- tune fast_period "
                "and slow_period to catch the current uptrend regime while "
                "avoiding whipsaws."
            ),
            (
                '{"trend_lifecycle": {"row_count": 140, "stage": "uptrend"}, '
                '"arima": {"row_count": 120, "forecast_return_pct": 0.021}, '
                '"regime_analysis": {"row_count": 100, "regime": "bull"}}'
            ),
        )
        low = output.lower()
        assert "recipe:" in low, (
            f"expected a RECIPE choice for a recipe-coverable ask; got:\n{output}\n(recorded {path})"
        )
        assert "crossover" in low, (
            f"expected the crossover recipe to be chosen; got:\n{output}\n(recorded {path})"
        )
        assert "param_grid" in low, (
            f"expected a PARAM_GRID in the recipe answer; got:\n{output}\n(recorded {path})"
        )

    def test_falls_back_to_raw_code_when_no_recipe_covers_it(self):
        output, path = self._run(
            "exception path: no recipe covers this ask",
            (
                "Generate a strategy idea for MSFT from 2023-01-01 to 2023-12-31: "
                "a pre-market-only strategy that reconstructs order-book imbalance "
                "from 1-minute bars and fades the opening gap when imbalance is "
                "extreme -- only trades in the first 15 minutes of each session."
            ),
            '{"momentum": {"row_count": 90, "forecast_return_pct": 0.008}}',
        )
        low = output.lower()
        assert "recipe:" not in low, (
            f"no recipe genuinely covers this ask; expected the raw-code path, got a RECIPE line:\n{output}\n(recorded {path})"
        )
        assert "no recipe" in low, (
            f"expected an explicit 'no recipe fits' statement on the exception path; got:\n{output}\n(recorded {path})"
        )
        assert "generate_weights" in output, (
            f"expected raw Python (generate_weights) on the exception path; got:\n{output}\n(recorded {path})"
        )


class TestAngleSynthesizerConsensus:
    """The real prompt + the real model reporting cross-angle consensus
    verdicts that match the deterministic compare_angles results (task 08,
    item 2)."""

    def _run(self, scenario: str, angle_data: str, compare_results: str) -> str:
        _require_live_model()
        system = _agent_prompt("screener", "angle_synthesizer")
        user = (
            "## Task\nSynthesize AAPL's angles and report the cross-angle "
            "consensus checks, exactly per your instructions.\n\n"
            "## get_all_angles(AAPL) result\n"
            f"{angle_data}\n\n"
            "## compare_angles results you already ran (report them faithfully)\n"
            f"{compare_results}\n\n"
            "Your final answer must cover: how many angles have data, what "
            "they show, the consensus verdict for each pair you checked, and "
            "whether any trade-plan calibration exists."
        )
        output = _chat(system, user)
        path = _record("angle_synthesizer", scenario, user, output)
        return output, path

    def test_reports_agree_diverge_and_insufficient_matching_tool_results(self):
        agree = compare_directional(
            "arima", 120, 0.021, "chronos", 80, 0.015,
        )
        diverge = compare_categorical(
            "regime_analysis", 120, "bear", "trend_lifecycle", 90, "uptrend",
        )
        insufficient = compare_directional(
            "kronos", 0, 0.0, "arima", 120, 0.021,
        )
        angle_data = (
            '{"arima": {"row_count": 120, "forecast_return_pct": 0.021}, '
            '"chronos": {"row_count": 80, "forecast_return_pct": 0.015}, '
            '"regime_analysis": {"row_count": 120, "regime": "bear"}, '
            '"trend_lifecycle": {"row_count": 90, "stage": "uptrend"}, '
            '"kronos": {"row_count": 0}}'
        )
        compare_results = "\n".join([
            f"- compare_angles(arima, chronos, directional) => {agree.outcome} | reasoning: {agree.reasoning}",
            f"- compare_angles(regime_analysis, trend_lifecycle, categorical) => {diverge.outcome} | reasoning: {diverge.reasoning}",
            f"- compare_angles(kronos, arima, directional) => {insufficient.outcome} | reasoning: {insufficient.reasoning}",
        ])
        output, path = self._run("agree + diverge + insufficient", angle_data, compare_results)
        low = output.lower()
        assert "agree" in low, (
            f"arima/chronos agree but the output never says so:\n{output}\n(recorded {path})"
        )
        assert "diverge" in low, (
            f"regime_analysis/trend_lifecycle diverge but the output never says so:\n{output}\n(recorded {path})"
        )
        assert "insufficient" in low or "no data" in low, (
            f"kronos has row_count=0 (insufficient_data) but the output never says so:\n{output}\n(recorded {path})"
        )

    def test_all_angles_empty_reports_plainly(self):
        angle_data = (
            '{"arima": {"row_count": 0}, "chronos": {"row_count": 0}, '
            '"regime_analysis": {"row_count": 0}, "trend_lifecycle": {"row_count": 0}, '
            '"kronos": {"row_count": 0}}'
        )
        output, path = self._run(
            "all angles empty",
            angle_data,
            "- compare_angles: all pairs insufficient_data (row_count=0 on both sides)",
        )
        low = output.lower()
        assert "0 of 28" in low or "no data" in low, (
            f"expected a plain 'N of 28 angles have data' statement for an all-empty case; got:\n{output}\n(recorded {path})"
        )