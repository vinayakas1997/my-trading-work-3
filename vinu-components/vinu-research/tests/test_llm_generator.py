from __future__ import annotations

import asyncio
import ast
import time

import numpy as np
import pandas as pd
import pytest

from vinu_research.llm_generator import LlmStrategyGenerator, _complexity_penalty, validate_code, validate_sandbox
from vinu_research.models import LlmCandidate

_VALID_STRATEGY = """from __future__ import annotations

import pandas as pd
import numpy as np

from vinu_simulator.engine.strategies import BaseStrategy


class UserStrategy(BaseStrategy):
    def __init__(self, period=20):
        self.period = period

    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        ma = data['close'].rolling(self.period).mean()
        signal = (data['close'] > ma).astype(int)
        signal = signal.fillna(0)
        return signal * 0.98
"""


class TestValidateCode:
    def test_valid_code_passes(self):
        assert validate_code(_VALID_STRATEGY) is True

    def test_syntax_error_fails(self):
        assert validate_code("class UserStrategy:") is False

    def test_missing_class_fails(self):
        code = "def generate_weights(data): pass"
        assert validate_code(code) is False

    def test_missing_method_fails(self):
        code = "class UserStrategy(BaseStrategy):\n    pass"
        assert validate_code(code) is False

    def test_wrong_class_name_fails(self):
        code = _VALID_STRATEGY.replace("UserStrategy", "MyStrategy")
        assert validate_code(code) is False

    def test_unsafe_eval_detected(self):
        code = _VALID_STRATEGY + "\nsignal = eval('1+1')"
        assert validate_code(code) is False

    def test_unsafe_exec_detected(self):
        code = _VALID_STRATEGY + "\nexec('x = 1')"
        assert validate_code(code) is False

    def test_unsafe_import_detected(self):
        code = _VALID_STRATEGY + "\nimport os\nos.system('ls')"
        assert validate_code(code) is False

    def test_valid_with_different_class_body_passes(self):
        code = _VALID_STRATEGY.replace("period=20", "fast=10, slow=30")
        assert validate_code(code) is True

    def test_empty_code_fails(self):
        assert validate_code("") is False


class TestValidateSandbox:
    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        n = 100
        return pd.DataFrame({
            "open": 100 + np.cumsum(rng.normal(0, 1, n)),
            "high": 100 + np.cumsum(rng.normal(0, 1, n)) + abs(rng.normal(0, 0.5, n)),
            "low": 100 + np.cumsum(rng.normal(0, 1, n)) - abs(rng.normal(0, 0.5, n)),
            "close": 100 + np.cumsum(rng.normal(0, 1, n)),
            "volume": np.abs(rng.normal(1_000_000, 200_000, n)),
        })

    def test_valid_strategy_passes_sandbox(self, sample_data):
        assert validate_sandbox(_VALID_STRATEGY, sample_data) is True

    def test_invalid_code_fails_sandbox(self, sample_data):
        assert validate_sandbox("invalid code", sample_data) is False

    def test_strategy_returning_non_series_fails(self, sample_data):
        code = _VALID_STRATEGY.replace("return signal * 0.98", "return 42")
        assert validate_sandbox(code, sample_data) is False

    def test_strategy_with_all_nan_fails(self, sample_data):
        code = _VALID_STRATEGY.replace("signal = signal.fillna(0)", "signal = pd.Series(float('nan'), index=data.index)")
        assert validate_sandbox(code, sample_data) is False


class TestComplexityPenalty:
    def test_zero_for_short_code(self):
        code = "class UserStrategy(BaseStrategy):\n    def generate_weights(self, data):\n        return data['close'] * 0"
        assert _complexity_penalty(code) == 0.0

    def test_positive_for_long_code(self):
        lines = [f"    x{i} = 1" for i in range(30)]
        code = "class UserStrategy(BaseStrategy):\n    def generate_weights(self, data):\n" + "\n".join(lines)
        penalty = _complexity_penalty(code)
        assert penalty > 0.0
        assert penalty <= 0.3

    def test_clips_at_30_pct(self):
        lines = [f"    x{i} = 1" for i in range(100)]
        code = "class UserStrategy(BaseStrategy):\n    def generate_weights(self, data):\n" + "\n".join(lines)
        assert _complexity_penalty(code) == 0.3

    def test_ignores_comments_and_imports(self):
        code = "# comment\nimport os\nfrom foo import bar\nx = 1"
        assert _complexity_penalty(code) == 0.0


class TestLlmCandidate:
    def test_default_values(self):
        c = LlmCandidate(code="code")
        assert c.features_required == []
        assert c.reasoning == ""
        assert c.params == {}
        assert c.validated is False

    def test_custom_values(self):
        c = LlmCandidate(
            code="code",
            features_required=["sma_20", "rsi_14"],
            reasoning="test",
            params={"period": 20},
            validated=True,
        )
        assert c.features_required == ["sma_20", "rsi_14"]
        assert c.reasoning == "test"
        assert c.params == {"period": 20}
        assert c.validated is True


class _SlowFakeLlmClient:
    """Each call takes a fixed delay — mirrors a real LLM round-trip, so serialized
    vs. concurrent execution produce measurably different total wall time."""

    def __init__(self, delay: float = 0.05):
        self._delay = delay
        self.call_count = 0

    def is_configured(self) -> bool:
        return True

    async def chat_json(self, system: str, user: str) -> dict:
        self.call_count += 1
        await asyncio.sleep(self._delay)
        return {
            "strategy_code": _VALID_STRATEGY,
            "features_required": [],
            "reasoning": "fake",
            "params": {},
        }


class TestLlmStrategyGeneratorConcurrency:
    async def test_candidates_generated_concurrently_not_sequentially(self):
        n_candidates = 4
        delay = 0.05
        client = _SlowFakeLlmClient(delay=delay)
        gen = LlmStrategyGenerator(client)

        start = time.perf_counter()
        candidates = await gen.generate(
            user_idea="SMA crossover", symbol="AAPL",
            from_date="2024-01-01", to_date="2024-12-31",
            n_candidates=n_candidates,
        )
        elapsed = time.perf_counter() - start

        assert len(candidates) == n_candidates
        assert client.call_count == n_candidates
        # Sequential would take >= n_candidates * delay; concurrent should take
        # roughly one delay's worth (with generous slack for scheduling overhead).
        assert elapsed < n_candidates * delay * 0.75

    async def test_one_failing_candidate_does_not_block_the_others(self):
        client = _SlowFakeLlmClient(delay=0.01)
        call_index = {"n": 0}

        async def flaky_chat_json(system: str, user: str) -> dict:
            call_index["n"] += 1
            if call_index["n"] == 2:
                raise RuntimeError("simulated LLM failure")
            await asyncio.sleep(0.01)
            return {
                "strategy_code": _VALID_STRATEGY,
                "features_required": [],
                "reasoning": "fake",
                "params": {},
            }

        client.chat_json = flaky_chat_json
        gen = LlmStrategyGenerator(client)
        candidates = await gen.generate(
            user_idea="SMA crossover", symbol="AAPL",
            from_date="2024-01-01", to_date="2024-12-31",
            n_candidates=3,
        )
        assert len(candidates) == 2
