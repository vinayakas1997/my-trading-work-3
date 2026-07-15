from __future__ import annotations

import numpy as np
import pytest

from vinu_features.compute.operators import (
    cs_rank,
    decay_linear,
    delta,
    rank,
    safe_div,
    scale,
    signed_power,
    ts_argmax,
    ts_argmin,
    ts_corr,
    ts_cov,
    ts_max,
    ts_mean,
    ts_min,
    ts_rank,
    ts_std,
    ts_sum,
    vwap,
    zscore,
)


class TestRank:
    def test_rank_2d(self):
        data = np.array([[3.0, 1.0, 2.0], [10.0, 20.0, 30.0]])
        r = rank(data)
        assert r[0, 0] == 1.0  # 3 is max in row
        assert r[0, 1] == 0.0  # 1 is min
        assert r[0, 2] == 0.5  # 2 is middle
        assert r[1, 0] == 0.0  # 10 is min in row 2
        assert r[1, 2] == 1.0  # 30 is max

    def test_rank_with_nan(self):
        data = np.array([[np.nan, 1.0, 2.0]])
        r = rank(data)
        assert np.isnan(r[0, 0])
        assert r[0, 2] == 1.0

    def test_cs_rank_alias(self):
        data = np.array([[3.0, 1.0, 2.0]])
        np.testing.assert_array_equal(cs_rank(data), rank(data))


class TestZScore:
    def test_zscore_standardizes(self):
        data = np.array([[1.0, 2.0, 3.0]])
        z = zscore(data)
        assert abs(np.nanmean(z)) < 1e-10  # mean approx 0
        assert abs(np.nanstd(z) - 1.0) < 0.1  # std approx 1 (ddof=0)


class TestScale:
    def test_scale_to_minus_one_one(self):
        data = np.array([[1.0, 3.0, 5.0]])
        s = scale(data)
        assert s[0, 0] == -1.0
        assert s[0, 2] == 1.0
        assert s[0, 1] == 0.0


class TestTsRank:
    def test_ts_rank(self):
        data = np.array([[1.0], [3.0], [2.0], [5.0], [4.0]])
        r = ts_rank(data, n=3)
        assert not np.isnan(r[2, 0])  # first valid after warmup
        assert 0 <= r[2, 0] <= 1.0


class TestTsCorr:
    def test_ts_corr(self):
        x = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]]).T
        y = np.array([[2.0, 4.0, 6.0, 8.0, 10.0]]).T
        c = ts_corr(x, y, n=3)
        assert abs(c[2, 0] - 1.0) < 0.01  # perfect correlation


class TestDelta:
    def test_delta(self):
        data = np.array([[1.0], [3.0], [6.0], [10.0]])
        d = delta(data, d=1)
        assert d[1, 0] == 2.0
        assert d[2, 0] == 3.0
        assert np.isnan(d[0, 0])

    def test_delta_d2(self):
        data = np.array([[1.0], [2.0], [4.0], [7.0]])
        d = delta(data, d=2)
        assert d[2, 0] == 3.0
        assert np.isnan(d[0, 0])
        assert np.isnan(d[1, 0])

    def test_delta_d1_raises_for_zero(self):
        with pytest.raises(AssertionError):
            delta(np.array([[1.0]]), d=0)


class TestDecayLinear:
    def test_decay_linear(self):
        data = np.array([[1.0], [2.0], [3.0], [4.0], [5.0]])
        d = decay_linear(data, n=3)
        # weights: 1/6, 2/6, 3/6 for most recent
        assert not np.isnan(d[2, 0])
        assert d[2, 0] == pytest.approx((1 * 1 + 2 * 2 + 3 * 3) / 6.0)


class TestSignedPower:
    def test_signed_power(self):
        data = np.array([[-2.0, -1.0, 0.0, 1.0, 2.0]])
        sp = signed_power(data, e=2.0)
        np.testing.assert_array_almost_equal(sp, np.array([[-4.0, -1.0, 0.0, 1.0, 4.0]]))


class TestSafeDiv:
    def test_safe_div(self):
        x = np.array([1.0, 2.0, 3.0, 0.0])
        y = np.array([2.0, 0.0, np.nan, 5.0])
        d = safe_div(x, y)
        assert d[0] == 0.5
        assert d[1] == 0.0  # y=0
        assert d[2] == 0.0  # y=nan
        assert d[3] == 0.0  # x=0 / y=5 = 0


class TestVWAP:
    def test_vwap(self):
        close = np.array([[100.0], [102.0], [101.0]])
        volume = np.array([[1000.0], [1500.0], [1200.0]])
        v = vwap(close, volume)
        expected = (100 * 1000) / 1000
        assert v[0, 0] == expected


class TestTsSum:
    def test_ts_sum(self):
        data = np.array([[1.0], [2.0], [3.0], [4.0], [5.0]])
        s = ts_sum(data, n=3)
        assert s[2, 0] == 6.0
        assert s[3, 0] == 9.0
        assert np.isnan(s[0, 0])

    def test_ts_mean(self):
        data = np.array([[1.0], [2.0], [3.0]])
        m = ts_mean(data, n=2)
        assert m[1, 0] == 1.5

    def test_ts_std(self):
        data = np.array([[1.0], [2.0], [3.0]])
        s = ts_std(data, n=2)
        assert s[1, 0] == 0.5  # std of [1, 2] = 0.5

    def test_ts_max(self):
        data = np.array([[1.0], [3.0], [2.0]])
        m = ts_max(data, n=3)
        assert m[2, 0] == 3.0

    def test_ts_min(self):
        data = np.array([[3.0], [1.0], [2.0]])
        m = ts_min(data, n=3)
        assert m[2, 0] == 1.0

    def test_ts_argmax(self):
        data = np.array([[1.0], [3.0], [2.0]])
        a = ts_argmax(data, n=3)
        assert a[2, 0] == 1.0  # position 1 (0-indexed) has max

    def test_ts_argmin(self):
        data = np.array([[3.0], [1.0], [2.0]])
        a = ts_argmin(data, n=3)
        assert a[2, 0] == 1.0  # position 1 (0-indexed) has min
