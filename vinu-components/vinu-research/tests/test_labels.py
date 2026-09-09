import numpy as np

from vinu_research.labels import triple_barrier_labels


def test_uptrend_labels_positive():
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(0.5 + rng.normal(0, 0.2, 60))
    out = triple_barrier_labels(close, max_hold=20)
    assert out[20] == 1


def test_downtrend_labels_negative():
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(-0.5 + rng.normal(0, 0.2, 60))
    out = triple_barrier_labels(close, max_hold=20)
    assert out[20] == -1


def test_flat_labels_timeout_zero():
    close = np.full(30, 100.0)
    out = triple_barrier_labels(close, max_hold=20)
    assert set(out.tolist()) == {0}


def test_no_lookahead_last_bar_zero():
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(0.5 + rng.normal(0, 0.2, 30))
    out = triple_barrier_labels(close, max_hold=20)
    assert out[-1] == 0
