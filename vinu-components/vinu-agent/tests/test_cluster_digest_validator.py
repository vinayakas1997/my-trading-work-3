from __future__ import annotations

from vinu_agent.tools.angle_clusters import ALL_REAL_ANGLE_IDS, ANGLE_CLUSTERS, ANGLE_TO_CLUSTER
from vinu_agent.tools.cluster_digest_validator import (
    find_angle_mentions,
    validate,
    validate_cluster_digest,
    validate_coverage_claim,
)


def test_all_28_real_angles_are_assigned_to_exactly_one_cluster():
    real_angle_ids = {
        "arima", "backtesting_44_metrics", "chronos", "dlinear",
        "drawdown_deep_dive", "exponential_smoothing", "garch",
        "itransformer", "kalman_filters", "kronos", "lag_llama",
        "lpatchtst", "lstm", "moirai", "moment", "news_price_causality",
        "patchtst", "peer_relative_strength", "pnl_attribution",
        "regime_analysis", "shock_clustering", "shock_personality",
        "tft", "timer_timerxl", "timesfm", "tips_regime_aware_transformer",
        "trend_lifecycle", "trend_session_structure",
    }
    assert real_angle_ids == ALL_REAL_ANGLE_IDS
    assert len(real_angle_ids) == 28
    assert set(ANGLE_CLUSTERS.keys()) == {"A", "B", "C", "D", "E", "F", "G"}


class TestFindAngleMentions:
    def test_matches_the_raw_underscored_id(self):
        assert "kalman_filters" in find_angle_mentions("kalman_filters shows a rising level")

    def test_matches_a_human_written_title_case_variant(self):
        # The real confirmed shape from the 9B run's Cluster B sentence:
        # "Kalman Filters" (spaces, title case) referring to kalman_filters.
        assert "kalman_filters" in find_angle_mentions(
            "Chronos, DLinear, iTransformer, Kalman Filters, LPatchTST..."
        )

    def test_does_not_false_positive_on_unrelated_text(self):
        assert find_angle_mentions("The market looks bullish today.") == set()


class TestValidateClusterDigest:
    def test_clean_digest_with_correct_membership_has_no_findings(self):
        digest = {
            "A": "ARIMA and Kalman Filters show a consistent upward bias.",
            "B": "PatchTST and LSTM both lean up with moderate confidence.",
        }
        assert validate_cluster_digest(digest) == []

    def test_real_confirmed_failure_kalman_filters_cited_under_cluster_b(self):
        """Reproduces the exact real finding from the 9B live run against
        hindsight-llm (2026-09-22, uneven-data test): Cluster B's own
        synthesis sentence named 'Kalman Filters' as a contributing
        member, but kalman_filters is a real Cluster A angle. See
        missing-pieces-of-system/angle-comprehension-hierarchy/
        03-real-llm-findings-and-guardrails.md."""
        digest = {
            "B": (
                "A strong consensus of 11 out of 14 models with data "
                "(Chronos, DLinear, iTransformer, Kalman Filters, LPatchTST, "
                "LSTM, PatchTST, TFT, Timer TimerXL, TimesFM, and Tips Regime "
                "Aware Transformer) lean up or flat-to-up."
            ),
        }
        findings = validate_cluster_digest(digest)
        assert len(findings) == 1
        assert findings[0].kind == "cross_cluster_mention"
        assert findings[0].cluster_key == "B"
        assert "kalman_filters" in findings[0].detail
        assert "cluster A" in findings[0].detail

    def test_unknown_cluster_key_is_flagged(self):
        digest = {"H": "some invented cluster the model made up"}
        findings = validate_cluster_digest(digest)
        assert len(findings) == 1
        assert findings[0].kind == "unknown_cluster_key"
        assert findings[0].cluster_key == "H"

    def test_empty_digest_is_valid(self):
        assert validate_cluster_digest({}) == []

    def test_every_real_angle_correctly_placed_in_its_own_cluster_sentence_is_clean(self):
        digest = {
            cluster: f"{', '.join(angles)} were reviewed this cycle."
            for cluster, angles in ANGLE_CLUSTERS.items()
        }
        assert validate_cluster_digest(digest) == []


class TestValidateCoverageClaim:
    def test_real_confirmed_failure_4b_undercounted_27_of_28(self):
        """Reproduces the exact real finding from the 4B live run
        (2026-09-22, clean-data test): the model stated 27 of 28 angles
        had data when the real, deterministic row-count sum was 28."""
        real_row_counts = {f"angle_{i}": 5 for i in range(28)}  # all 28 have data
        matches, real_count = validate_coverage_claim(27, real_row_counts)
        assert matches is False
        assert real_count == 28

    def test_matching_claim_passes(self):
        real_row_counts = {"a": 3, "b": 0, "c": 5}
        matches, real_count = validate_coverage_claim(2, real_row_counts)
        assert matches is True
        assert real_count == 2

    def test_zero_row_count_does_not_count_as_having_data(self):
        matches, real_count = validate_coverage_claim(1, {"a": 0, "b": 2})
        assert real_count == 1
        assert matches is True


class TestValidateEndToEnd:
    def test_bundles_cluster_and_coverage_checks(self):
        digest = {"B": "Kalman Filters and PatchTST both lean up."}
        report = validate(
            digest,
            stated_coverage_count=26,
            angle_row_counts={f"angle_{i}": 1 for i in range(28)},
        )
        assert report.ok is False
        assert len(report.cluster_findings) == 1
        assert report.coverage_mismatch is True
        assert report.coverage_real == 28

    def test_clean_report_is_ok(self):
        digest = {"A": "ARIMA trending up."}
        report = validate(
            digest,
            stated_coverage_count=28,
            angle_row_counts={f"angle_{i}": 1 for i in range(28)},
        )
        assert report.ok is True
