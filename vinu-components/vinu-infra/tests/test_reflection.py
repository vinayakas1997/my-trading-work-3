import json

import pytest

from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    POLARITY_LOWER_IS_WORSE,
    ReflectionStore,
    SEVERITY_NOTABLE,
    SEVERITY_SIGNIFICANT,
    TREND_DEGRADING,
    TREND_IMPROVING,
    TREND_STABLE,
    classify_severity,
    compute_trend,
    pearson_correlation,
    population_stability_index,
    write_finding,
    write_findings,
)


def _finding(**overrides) -> Finding:
    base = dict(
        analyst_name="decision_process",
        cluster="Decision-Process / Cognition",
        scope_type="system",
        scope_key="orchestrator",
        signal_json={"retry_rejection_delta": 0.3},
        evidence_count=40,
        primary_metric=0.3,
        metric_name="retry_rejection_delta",
        psi=0.3,
    )
    base.update(overrides)
    return Finding(**base)


class TestPopulationStabilityIndex:
    def test_identical_distributions_are_zero_ish(self):
        values = [float(i) for i in range(100)]
        psi = population_stability_index(values, values)
        assert psi < 0.01

    def test_shifted_distribution_is_large(self):
        reference = [float(i) for i in range(100)]
        current = [float(i) + 500 for i in range(100)]
        psi = population_stability_index(reference, current)
        assert psi > 0.25

    def test_empty_inputs_return_zero(self):
        assert population_stability_index([], [1.0, 2.0]) == 0.0
        assert population_stability_index([1.0, 2.0], []) == 0.0

    def test_never_negative(self):
        reference = [1.0, 2.0, 3.0, 4.0, 5.0] * 20
        current = [1.0, 1.5, 2.5, 3.5, 4.5] * 20
        assert population_stability_index(reference, current) >= 0.0


class TestPearsonCorrelation:
    def test_perfect_positive_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        assert pearson_correlation(xs, ys) == pytest.approx(1.0, abs=1e-9)

    def test_perfect_negative_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [5.0, 4.0, 3.0, 2.0, 1.0]
        assert pearson_correlation(xs, ys) == pytest.approx(-1.0, abs=1e-9)

    def test_no_relationship_is_near_zero(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [3.0, 3.0, 3.0, 3.0001]
        assert abs(pearson_correlation(xs, ys)) < 1.0

    def test_fewer_than_two_points_returns_zero(self):
        assert pearson_correlation([], []) == 0.0
        assert pearson_correlation([1.0], [2.0]) == 0.0

    def test_zero_variance_series_returns_zero(self):
        assert pearson_correlation([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0
        assert pearson_correlation([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) == 0.0

    def test_mismatched_lengths_uses_shorter(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0]
        assert pearson_correlation(xs, ys) == pytest.approx(1.0, abs=1e-9)


class TestClassifySeverity:
    def test_routine_below_threshold(self):
        assert classify_severity(0.05) is None

    def test_notable_in_band(self):
        assert classify_severity(0.15) == SEVERITY_NOTABLE

    def test_significant_above_band(self):
        assert classify_severity(0.4) == SEVERITY_SIGNIFICANT

    def test_domain_floor_forces_significant_even_at_low_psi(self):
        assert classify_severity(0.0, domain_floor_breached=True) == SEVERITY_SIGNIFICANT


class TestComputeTrend:
    def test_no_prior_is_stable(self):
        assert compute_trend(None, 0.5, POLARITY_HIGHER_IS_WORSE) == TREND_STABLE

    def test_small_relative_change_is_stable(self):
        assert compute_trend(0.30, 0.31, POLARITY_HIGHER_IS_WORSE) == TREND_STABLE

    def test_higher_is_worse_rising_is_degrading(self):
        assert compute_trend(0.20, 0.40, POLARITY_HIGHER_IS_WORSE) == TREND_DEGRADING

    def test_higher_is_worse_falling_is_improving(self):
        assert compute_trend(0.40, 0.20, POLARITY_HIGHER_IS_WORSE) == TREND_IMPROVING

    def test_lower_is_worse_falling_is_degrading(self):
        assert compute_trend(0.80, 0.40, POLARITY_LOWER_IS_WORSE) == TREND_DEGRADING

    def test_lower_is_worse_rising_is_improving(self):
        assert compute_trend(0.40, 0.80, POLARITY_LOWER_IS_WORSE) == TREND_IMPROVING

    def test_prior_zero_nonzero_new_is_full_change(self):
        assert compute_trend(0.0, 0.01, POLARITY_HIGHER_IS_WORSE) == TREND_DEGRADING

    def test_prior_and_new_both_zero_is_stable(self):
        assert compute_trend(0.0, 0.0, POLARITY_HIGHER_IS_WORSE) == TREND_STABLE


class TestReflectionStoreSchema:
    def test_tables_created(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        conn = store._get_conn()
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert {
            "reflection_findings_history",
            "reflection_beliefs",
            "reflection_reference_config",
        } <= names

    def test_reference_config_round_trip(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        store.upsert_reference_config(
            analyst_name="decision_process",
            scope_type="system",
            metric_name="retry_rejection_delta",
            metric_polarity=POLARITY_HIGHER_IS_WORSE,
            reason="initial seed",
        )
        cfg = store.get_reference_config("decision_process", "system", "retry_rejection_delta")
        assert cfg is not None
        assert cfg["metric_polarity"] == POLARITY_HIGHER_IS_WORSE
        assert cfg["reason"] == "initial seed"

    def test_reference_config_upsert_is_idempotent_not_duplicating(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        for _ in range(3):
            store.upsert_reference_config(
                analyst_name="decision_process",
                scope_type="system",
                metric_name="retry_rejection_delta",
                metric_polarity=POLARITY_HIGHER_IS_WORSE,
            )
        conn = store._get_conn()
        count = conn.execute("SELECT COUNT(*) AS c FROM reflection_reference_config").fetchone()
        assert count["c"] == 1

    def test_missing_reference_config_returns_none(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        assert store.get_reference_config("nobody", "system", "nothing") is None


class TestWriteFinding:
    def test_routine_writes_nothing(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        finding = _finding(psi=0.02)
        result = write_finding(store, finding)
        assert result is None
        assert store.list_findings() == []
        assert store.list_beliefs() == []

    def test_significant_writes_both_tables(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        store.upsert_reference_config(
            analyst_name="decision_process",
            scope_type="system",
            metric_name="retry_rejection_delta",
            metric_polarity=POLARITY_HIGHER_IS_WORSE,
        )
        finding = _finding(psi=0.4, primary_metric=0.35)
        finding_id = write_finding(store, finding)
        assert finding_id is not None

        history = store.list_findings("decision_process")
        assert len(history) == 1
        assert history[0]["severity"] == SEVERITY_SIGNIFICANT
        assert json.loads(history[0]["signal_json"]) == {"retry_rejection_delta": 0.3}

        belief = store.get_belief("decision_process", "system", "orchestrator")
        assert belief is not None
        assert belief["trend"] == TREND_STABLE  # first-ever belief for this scope
        assert belief["primary_metric"] == 0.35

    def test_second_write_diffs_trend_against_prior_belief(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        store.upsert_reference_config(
            analyst_name="decision_process",
            scope_type="system",
            metric_name="retry_rejection_delta",
            metric_polarity=POLARITY_HIGHER_IS_WORSE,
        )
        write_finding(store, _finding(psi=0.3, primary_metric=0.20))
        write_finding(store, _finding(psi=0.3, primary_metric=0.50))

        belief = store.get_belief("decision_process", "system", "orchestrator")
        assert belief["trend"] == TREND_DEGRADING  # higher_is_worse, metric rose
        assert belief["primary_metric"] == 0.50

        history = store.list_findings("decision_process")
        assert len(history) == 2  # append-only

    def test_missing_reference_config_falls_back_to_stable_not_raise(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        # No upsert_reference_config call at all.
        write_finding(store, _finding(psi=0.3, primary_metric=0.2))
        result = write_finding(store, _finding(psi=0.3, primary_metric=0.9))
        assert result is not None
        belief = store.get_belief("decision_process", "system", "orchestrator")
        assert belief["trend"] in (TREND_DEGRADING, TREND_IMPROVING, TREND_STABLE)


class TestWriteFindings:
    def test_skips_routine_keeps_significant(self, tmp_path):
        store = ReflectionStore(tmp_path / "reflection.db")
        store.upsert_reference_config(
            analyst_name="decision_process",
            scope_type="system",
            metric_name="retry_rejection_delta",
            metric_polarity=POLARITY_HIGHER_IS_WORSE,
        )
        findings = [
            _finding(scope_key="orchestrator", psi=0.02),  # routine -> skipped
            _finding(scope_key="forecast_skill", psi=0.3),  # written
        ]
        written = write_findings(store, findings)
        assert len(written) == 1
        assert store.get_belief("decision_process", "system", "orchestrator") is None
        assert store.get_belief("decision_process", "system", "forecast_skill") is not None
