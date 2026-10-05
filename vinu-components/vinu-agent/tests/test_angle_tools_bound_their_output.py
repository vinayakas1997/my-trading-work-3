"""The angle tools put every stored row of an angle into the model's prompt. META cluster F was 9.7 MB, which overflowed
the local model's context (HTTP 500 'Context size has been exceeded') for every ticker the planner bootstrapped."""

import json

from vinu_agent.tools.angles_tool import _MAX_PAYLOAD_CHARS, _bounded_payload


def _angle(n, pad=0):
    return {"angle": "a", "row_count": n, "data": [{"date": i, "v": i, "pad": "x" * pad} for i in range(n)]}


def test_the_newest_rows_are_kept_and_the_true_count_is_reported():
    out = json.loads(_bounded_payload({"angles": {"a": _angle(500)}}))["angles"]["a"]
    assert out["row_count"] == 500 and out["rows_total"] == 500 and out["truncated"] is True
    assert out["data"][-1]["date"] == 499 and len(out["data"]) == out["rows_shown"] <= 30


def test_a_small_angle_is_left_untouched():
    out = json.loads(_bounded_payload({"angles": {"a": _angle(5)}}))["angles"]["a"]
    assert len(out["data"]) == 5 and "truncated" not in out


def test_nested_all_timeframes_shape_is_bounded_too():
    nested = {"angles": {"a": {tf: _angle(2000, pad=200) for tf in ("15min", "1H", "4H", "1D", "1min", "5min")}}}
    text = _bounded_payload(nested)
    assert len(text) <= _MAX_PAYLOAD_CHARS * 2          # shrunk through the steps, nowhere near megabytes
    assert json.loads(text)["angles"]["a"]["1D"]["data"][-1]["date"] == 1999
