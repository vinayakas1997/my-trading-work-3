from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.storage.query import query_slice, unnest_predictions


def test_query_slice_always_attaches_n():
    df = pd.DataFrame({
        "session": ["ny", "ny", "london", "ny"],
        "hit": [1, 0, 1, 1],
    })
    out = query_slice(df, ["session"], {"avg_hit_rate": ("hit", "mean")})
    assert set(out.columns) == {"session", "n", "avg_hit_rate"}
    ny_row = out[out["session"] == "ny"].iloc[0]
    assert ny_row["n"] == 3
    assert abs(ny_row["avg_hit_rate"] - 2 / 3) < 1e-9


def test_query_slice_thin_group_still_reports_n():
    # A 2-observation "100% success rate" must carry n=2 so it's visibly
    # thin, not indistinguishable from a well-supported average.
    df = pd.DataFrame({"session": ["closed", "closed"], "hit": [1, 1]})
    out = query_slice(df, ["session"], {"avg_hit_rate": ("hit", "mean")})
    assert out.iloc[0]["n"] == 2
    assert out.iloc[0]["avg_hit_rate"] == 1.0


def test_query_slice_empty_df_returns_empty_with_expected_columns():
    df = pd.DataFrame(columns=["session", "hit"])
    out = query_slice(df, ["session"], {"avg_hit_rate": ("hit", "mean")})
    assert list(out.columns) == ["session", "n", "avg_hit_rate"]
    assert len(out) == 0


def test_unnest_predictions_expands_one_row_per_horizon():
    df = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "predictions": [
            {1: {"hit": 1, "pinball": 0.1}, 2: {"hit": 0, "pinball": 0.2}},
            {1: {"hit": 1, "pinball": 0.15}},
        ],
    })
    flat = unnest_predictions(df)
    assert len(flat) == 3
    assert set(flat["horizon"]) == {1, 2}
    assert "predictions" not in flat.columns


def test_unnest_predictions_is_noop_without_predictions_column():
    df = pd.DataFrame({"session": ["ny"], "hit": [1]})
    flat = unnest_predictions(df)
    pd.testing.assert_frame_equal(flat, df)


def test_query_slice_after_unnest_groups_by_horizon():
    df = pd.DataFrame({
        "predictions": [
            {1: {"hit": 1}, 2: {"hit": 0}},
            {1: {"hit": 1}},
        ],
    })
    flat = unnest_predictions(df)
    out = query_slice(flat, ["horizon"], {"avg_hit_rate": ("hit", "mean")})
    h1 = out[out["horizon"] == 1].iloc[0]
    assert h1["n"] == 2
    assert h1["avg_hit_rate"] == 1.0
    h2 = out[out["horizon"] == 2].iloc[0]
    assert h2["n"] == 1
    assert h2["avg_hit_rate"] == 0.0
