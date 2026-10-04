"""features-logic-checking: Track 2 move detection worked out by hand. A move is real when the last close changed by
more than multiplier x ATR(14) (default 2.0)."""

from __future__ import annotations

import pandas as pd
import pytest

from vinu_live.live_decision.detector import detect_move


def _bars(*closes: float) -> pd.DataFrame:
    return pd.DataFrame({"close": list(closes)})


def test_a_move_larger_than_two_atr_is_detected_up():
    # ATR 2.0 -> threshold 4.0; 100 -> 105 is +5 > 4
    r = detect_move(_bars(100.0, 105.0), {"atr_14": 2.0})
    assert r["move_detected"] is True and r["direction"] == "up"
    assert r["price_move"] == pytest.approx(5.0) and r["threshold"] == pytest.approx(4.0)


def test_a_move_smaller_than_the_threshold_is_not_a_move():
    assert detect_move(_bars(100.0, 103.0), {"atr_14": 2.0})["move_detected"] is False   # +3 < 4


def test_a_fall_is_detected_down_and_exactly_the_threshold_is_not_enough():
    assert detect_move(_bars(100.0, 95.0), {"atr_14": 2.0})["direction"] == "down"        # -5, beyond 4
    assert detect_move(_bars(100.0, 104.0), {"atr_14": 2.0})["move_detected"] is False    # +4 is not > 4


def test_cannot_tell_is_none_never_quiet():
    assert detect_move(_bars(100.0), {"atr_14": 2.0}) is None            # one bar
    assert detect_move(_bars(100.0, 105.0), {}) is None                  # ATR not computable yet (warm-up)
    assert detect_move(_bars(100.0, 105.0), {"atr_14": 0.0}) is None     # a zero ATR cannot define a threshold
