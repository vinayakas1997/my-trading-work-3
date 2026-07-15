from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import numpy as np

from vinu_features.compute.alpha_bench import run_bench, run_compare
from vinu_features.compute.alpha_meta import ALPHA_THEMES, AlphaMeta
from vinu_features.compute.alpha_registry import Registry


class TestAlphaMeta:
    def test_valid_themes(self):
        assert "momentum" in ALPHA_THEMES
        assert "reversal" in ALPHA_THEMES
        assert len(ALPHA_THEMES) == 11

    def test_create_meta(self):
        meta = AlphaMeta(
            id="alpha001",
            theme="momentum",
            formula_latex="rank(close / ts_mean(close, 20))",
        )
        assert meta.id == "alpha001"
        assert meta.theme == "momentum"
        assert "close" in meta.columns_required


class TestRegistry:
    def test_empty_registry(self):
        tmp = tempfile.mkdtemp()
        reg = Registry(Path(tmp))
        assert reg.list_alphas() == []
        assert reg.count() == 0

    def test_scan_alpha_file(self):
        tmp = Path(tempfile.mkdtemp())
        alpha_dir = tmp / "alpha_factors"
        alpha_dir.mkdir(parents=True)
        alpha_file = alpha_dir / "alpha001.py"
        alpha_file.write_text(
            '__alpha_meta__ = {\n'
            '    "id": "alpha001",\n'
            '    "theme": "momentum",\n'
            '    "formula_latex": "rank(close_20d)",\n'
            '    "columns_required": ["close"],\n'
            '}\n'
        )
        reg = Registry(tmp)
        modules = reg.list_alphas()
        assert len(modules) == 1
        assert modules[0].meta.id == "alpha001"
        assert modules[0].meta.theme == "momentum"

    def test_get_by_id(self):
        tmp = Path(tempfile.mkdtemp())
        alpha_dir = tmp / "alpha_factors"
        alpha_dir.mkdir(parents=True)
        (alpha_dir / "test_alpha.py").write_text(
            '__alpha_meta__ = {"id": "test_123", "theme": "volatility"}\n'
        )
        reg = Registry(tmp)
        module = reg.get("test_123")
        assert module is not None
        assert module.meta.theme == "volatility"

    def test_skips_file_without_meta(self):
        tmp = Path(tempfile.mkdtemp())
        alpha_dir = tmp / "alpha_factors"
        alpha_dir.mkdir(parents=True)
        (alpha_dir / "no_meta.py").write_text("x = 1\n")
        reg = Registry(tmp)
        assert reg.count() == 0


class TestAlphaBench:
    def test_bench_alive_alpha(self):
        rng = np.random.default_rng(42)
        values = {"alpha1": rng.normal(0.5, 0.1, 100)}
        fwd_returns = rng.normal(0.01, 0.02, 100)
        results = run_bench(values, fwd_returns)
        assert "alpha1" in results
        assert results["alpha1"]["status"] in ("alive", "dead", "reversed")

    def test_bench_insufficient_data(self):
        values = {"alpha1": np.array([1.0, 2.0])}
        fwd_returns = np.array([0.01, 0.02])
        results = run_bench(values, fwd_returns, min_periods=10)
        assert results["alpha1"]["status"] == "insufficient_data"

    def test_compare_ranks_by_ic(self):
        values = {
            "alpha1": np.array([1.0, 2.0, 3.0, 4.0, 5.0] * 10),
            "alpha2": np.array([5.0, 4.0, 3.0, 2.0, 1.0] * 10),
        }
        fwd = np.array([-0.01, 0.0, 0.01, 0.02, 0.03] * 10)
        ranked = run_compare(values, fwd)
        assert len(ranked) >= 1

    def test_compare_only_specific(self):
        values = {
            "alpha1": np.random.default_rng(42).normal(0, 1, 50),
            "alpha2": np.random.default_rng(43).normal(0, 1, 50),
        }
        fwd = np.random.default_rng(44).normal(0, 0.01, 50)
        ranked = run_compare(values, fwd, only=["alpha1"])
        assert all(r["alpha_id"] == "alpha1" for r in ranked)
