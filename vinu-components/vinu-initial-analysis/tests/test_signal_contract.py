import pandas as pd

from vinu_initial_analysis.angles.signal_contract import tag_row, SIGNAL_USAGE_CONTRACT
from vinu_initial_analysis.angles.regime_analysis.compute import compute as compute_regime


def test_tag_row_attaches_known_field():
    row = {"significance_score": 0.7}
    tag_row(row, "significance_score")
    assert row["significance_score_not_proven_for"] == ["direction", "sign_of_price_move"]
    assert row["significance_score_proven_for"] == ["magnitude_prioritization", "surprise_prediction"]
    assert row["significance_score_evidence_ref"]


def test_tag_row_noop_for_unknown_field():
    row = {"foo": 1}
    tag_row(row, "foo")
    assert row == {"foo": 1}


def test_tag_row_matches_registry_contents():
    row = {}
    tag_row(row, "regime_feature")
    contract = SIGNAL_USAGE_CONTRACT["regime_feature"]
    assert row["regime_feature_proven_for"] == contract["proven_for"]
    assert row["regime_feature_not_proven_for"] == contract["not_proven_for"]


def test_regime_analysis_output_carries_usage_tags():
    bars = pd.DataFrame({
        "close": [100 + (i % 5) * 0.3 - (i % 7) * 0.2 for i in range(40)],
    })
    df = compute_regime("AAPL", bars=bars)
    stats_rows = df[df.get("metric") == "regime_stats"] if not df.empty else df
    assert not stats_rows.empty
    assert "regime_feature_not_proven_for" in stats_rows.columns
    for tags in stats_rows["regime_feature_not_proven_for"]:
        assert "direction_prediction" in tags
