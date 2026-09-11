"""Stage C (C13): data-derived stress windows."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_research.regime_windows import derive_regime_windows


def _path(segments: list[tuple[float, float, int]]) -> pd.Series:
    """Build a daily price series from (start, end, n_days) linear segments."""
    vals: list[float] = []
    for start, end, n in segments:
        vals.extend(np.linspace(start, end, n).tolist())
    idx = pd.date_range("2021-01-01", periods=len(vals), freq="D")
    return pd.Series(vals, index=idx)


class TestDeriveRegimeWindows:
    def test_finds_drawdown_runup_and_decline(self) -> None:
        # rise 100->140, crash 140->90, recover 90->130
        s = _path([(100, 140, 150), (140, 90, 80), (90, 130, 170)])
        got = {name for name, _, _ in derive_regime_windows(s)}
        assert got == {"derived_max_drawdown", "derived_max_runup", "derived_steepest_decline"}

    def test_drawdown_window_brackets_the_peak_and_trough(self) -> None:
        s = _path([(100, 140, 150), (140, 90, 80), (90, 130, 170)])
        dd = next(w for w in derive_regime_windows(s) if w[0] == "derived_max_drawdown")
        _, f, t = dd
        # peak is ~day 150, trough ~day 230
        assert pd.Timestamp("2021-05-01") < pd.Timestamp(f) < pd.Timestamp("2021-06-15")
        assert pd.Timestamp("2021-08-01") < pd.Timestamp(t) < pd.Timestamp("2021-09-15")
        assert pd.Timestamp(t) > pd.Timestamp(f)

    def test_windows_are_in_config_tuple_shape(self) -> None:
        s = _path([(100, 140, 150), (140, 90, 80), (90, 130, 170)])
        for w in derive_regime_windows(s):
            assert len(w) == 3
            assert isinstance(w[0], str)
            pd.Timestamp(w[1])  # parses
            pd.Timestamp(w[2])

    def test_flat_series_yields_nothing(self) -> None:
        idx = pd.date_range("2021-01-01", periods=100, freq="D")
        assert derive_regime_windows(pd.Series([100.0] * 100, index=idx)) == []

    def test_short_series_yields_nothing(self) -> None:
        s = _path([(100, 90, 8)])
        assert derive_regime_windows(s) == []

    def test_none_input(self) -> None:
        assert derive_regime_windows(None) == []

    def test_monotonic_rise_has_a_runup_but_no_drawdown(self) -> None:
        s = _path([(100, 200, 300)])
        names = {name for name, _, _ in derive_regime_windows(s)}
        assert "derived_max_drawdown" not in names
        assert "derived_max_runup" in names

    def test_tiny_windows_are_filtered_by_min_window_days(self) -> None:
        # a 3-day dip inside a long rise: below min_window_days, dropped
        s = _path([(100, 150, 200), (150, 148, 3), (148, 250, 200)])
        for _, f, t in derive_regime_windows(s, min_window_days=15):
            assert (pd.Timestamp(t) - pd.Timestamp(f)).days >= 15

    def test_cumulative_return_path_works_the_same(self) -> None:
        rng = np.random.default_rng(0)
        rets = pd.Series(rng.normal(0.0003, 0.02, 400),
                         index=pd.date_range("2021-01-01", periods=400, freq="D"))
        path = (1 + rets).cumprod()
        got = derive_regime_windows(path)
        assert 1 <= len(got) <= 3
