from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from vinu_initial_analysis.storage.factsheet import (
    JudgmentLanguageError,
    NoRunFoundError,
    UnmappedColumnsError,
    generate_factsheet,
    write_factsheet,
    write_summary,
)
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import AngleStorage


def _arima_rows(n: int = 4, timeframe: str = "1D") -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "bar_ts": 1_700_000_000 + i * 86400,
            "step_index": i,
            "session": "closed",
            "subsession": None,
            "day_of_week": ["monday", "tuesday"][i % 2],
            "week_of_month": 1,
            "month": 7,
            "quarter": 3,
            "timeframe": timeframe,
            "status": "ok",
            "n_observations": 100,
            "order": {"p": 2, "d": 1, "q": 2},
            "aic": 500.0 + i,
            "forecast": 300.0 + i,
            "confidence_interval": [290.0, 310.0],
            "confidence_level": 0.95,
            "actual_price": 301.0 + i,
            "hit": 1 if i % 2 == 0 else 0,
            "abs_error": float(i),
            "squared_error": float(i * i),
        })
    return pd.DataFrame(rows)


class _Fixture:
    def __init__(self, tmp: str):
        self.tmp = tmp
        self.run_log = RunLog(Path(tmp) / "runs.db")
        self.storage = AngleStorage(tmp, run_log=self.run_log)

    def write_run(self, df: pd.DataFrame, *, granularity: str = "1D", **run_log_kwargs) -> str:
        run_id = self.storage.write("AAPL", "arima", df, granularity=granularity, tier="tier2")
        self.run_log.record_run(
            "AAPL", "arima", run_id, row_count=len(df), granularity=granularity, tier="tier2",
            **run_log_kwargs,
        )
        return run_id

    def close(self):
        self.run_log.close()


@pytest.fixture
def fixture():
    with TemporaryDirectory() as tmp:
        fx = _Fixture(tmp)
        try:
            yield fx
        finally:
            fx.close()


def test_paragraph_defines_every_term_used_in_the_table(fixture):
    fixture.write_run(_arima_rows())
    text = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    # Real angle purpose/output text, pulled from spec.yaml via the catalog.
    assert "AutoRegressive Integrated Moving Average" in text
    # hit_rate and n must be explained in-line, not assumed known.
    assert "hit_rate" in text
    assert "landed inside that step" in text
    # Every session row label must have its real UTC range stated.
    for label in ("closed", "london", "ny_premarket", "ny_regular", "ny_afterhours"):
        assert f"`{label}`" in text
    assert "UTC" in text


def test_condition_line_states_real_n_observations(fixture):
    fixture.write_run(_arima_rows())
    text = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    assert "N=100 candles" in text
    assert "at that column's own resolution" in text


def test_table_has_one_row_per_session_and_one_column_per_declared_time_format(fixture):
    fixture.write_run(_arima_rows())
    text = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    # ARIMA's real spec.yaml declares all 6 time formats.
    header_line = [l for l in text.splitlines() if l.startswith("| session |")][0]
    for tf in ("1min", "5min", "15min", "1H", "4H", "1D"):
        assert tf in header_line
    for label in ("closed", "london", "ny_premarket", "ny_regular", "ny_afterhours"):
        assert any(l.startswith(f"| {label} |") for l in text.splitlines())


def test_real_cell_carries_n_and_run_id_and_computed_at(fixture):
    run_id = fixture.write_run(_arima_rows())
    text = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    assert f"run_id={run_id}" in text
    assert "computed_at=" in text
    assert "n=4" in text


def test_uncomputed_cells_say_not_available(fixture):
    fixture.write_run(_arima_rows())  # only 1D has a real run
    text = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    assert "not available" in text
    # 1min was never run -- must not silently show a number for it.
    lines = [l for l in text.splitlines() if l.startswith("| closed |")]
    assert "not available" in lines[0]


def test_no_banned_words_in_a_real_generated_sheet(fixture):
    fixture.write_run(_arima_rows())
    text = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    lowered = text.lower()
    for word in ["good", "bad", "weak", "strong", "better", "worse", "recommend"]:
        assert word not in lowered


def test_unmapped_real_column_raises_instead_of_being_silently_dropped(fixture):
    df = _arima_rows()
    df["mystery_new_field"] = 1
    fixture.write_run(df)
    with pytest.raises(UnmappedColumnsError, match="mystery_new_field"):
        generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)


def test_angle_with_no_hand_authored_manifest_still_works_generically(fixture):
    # kalman_filters has no FIELD_MANIFESTS entry -- must fall back to the
    # generic auto-classifier rather than raising, since the whole point of
    # this pass was making the generator work for all 28 angles, not just
    # the one with a hand-written manifest.
    df = pd.DataFrame([
        {
            "bar_ts": 1_700_000_000 + i * 86400, "step_index": i,
            "session": "closed", "subsession": None, "day_of_week": "monday",
            "week_of_month": 1, "month": 7, "quarter": 3, "timeframe": "1D",
            "status": "ok", "filtered_trend": 0.5 + i * 0.01, "signal": 1,
        }
        for i in range(5)
    ])
    run_id = fixture.storage.write("AAPL", "kalman_filters", df, granularity="1D", tier="tier2")
    fixture.run_log.record_run("AAPL", "kalman_filters", run_id, row_count=len(df), granularity="1D", tier="tier2")
    text = generate_factsheet("AAPL", "kalman_filters", fixture.run_log, fixture.storage)
    assert "filtered_trend" in text
    assert "n=5" in text


def test_auto_classified_angle_never_averages_calendar_tag_columns(fixture):
    # Real bug found in a real batch run: `month`/`quarter`/`week_of_month`
    # have no hand-authored manifest entry for most angles, so the generic
    # classifier used to fall through to its numeric branch and average
    # them -- e.g. a real generated sheet showed `month=7.69`, a meaningless
    # number. Varying month/quarter per row here so a silent average would
    # produce a non-integer value distinguishable from any single real row.
    df = pd.DataFrame([
        {
            "bar_ts": 1_700_000_000 + i * 86400, "step_index": i,
            "session": "closed", "subsession": None, "day_of_week": "monday",
            "week_of_month": (i % 4) + 1, "month": (i % 3) + 1, "quarter": (i % 2) + 1,
            "timeframe": "1D", "status": "ok", "score": 1.0 + i,
        }
        for i in range(6)
    ])
    run_id = fixture.storage.write("AAPL", "kalman_filters", df, granularity="1D", tier="tier2")
    fixture.run_log.record_run("AAPL", "kalman_filters", run_id, row_count=len(df), granularity="1D", tier="tier2")
    text = generate_factsheet("AAPL", "kalman_filters", fixture.run_log, fixture.storage)
    # `score` is the only real mean field -- month/quarter/week_of_month
    # must never appear as an averaged value in the session table's cell.
    session_table_line = [l for l in text.splitlines() if l.startswith("| closed |")][0]
    assert "month=" not in session_table_line
    assert "quarter=" not in session_table_line
    assert "week_of_month=" not in session_table_line
    assert "score=" in session_table_line


def test_calendar_tag_breakdown_groups_by_real_observed_values(fixture):
    fixture.write_run(_arima_rows(n=4))  # day_of_week alternates monday/tuesday
    text = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    assert "## Breakdown by calendar tag" in text
    assert "### day_of_week" in text
    assert any(l.startswith("| monday |") for l in text.splitlines())
    assert any(l.startswith("| tuesday |") for l in text.splitlines())
    # month/quarter/week_of_month are constant (7/3/1) across all 4 fixture
    # rows -- only the real observed value becomes a row, no fabricated
    # placeholder rows for months/quarters that never occurred.
    assert any(l.startswith("| 7 |") for l in text.splitlines())
    assert not any(l.startswith("| 8 |") for l in text.splitlines())


def test_horizon_breakdown_unnests_real_nested_predictions(fixture):
    df = pd.DataFrame([
        {
            "bar_ts": 1_700_000_000 + i * 3600, "step_index": i,
            "session": "closed", "subsession": None, "day_of_week": "monday",
            "week_of_month": 1, "month": 7, "quarter": 3, "timeframe": "1H",
            "status": "ok",
            "predictions": {"1": {"median": 100.0 + i, "hit": i % 2}, "2": {"median": 101.0 + i, "hit": 1}},
        }
        for i in range(4)
    ])
    run_id = fixture.storage.write("AAPL", "chronos", df, granularity="1H", tier="tier2")
    fixture.run_log.record_run("AAPL", "chronos", run_id, row_count=len(df), granularity="1H", tier="tier2")
    text = generate_factsheet("AAPL", "chronos", fixture.run_log, fixture.storage)
    assert "## Breakdown by forecast horizon step" in text
    assert any(l.startswith("| 1 |") for l in text.splitlines())
    assert any(l.startswith("| 2 |") for l in text.splitlines())
    assert "hit=1" in text  # horizon=2 rows are all hit=1 in this fixture


def test_no_completed_run_raises(fixture):
    with pytest.raises(NoRunFoundError):
        generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)


def test_judgment_language_arriving_through_real_data_is_still_caught(fixture):
    df = _arima_rows()
    df["status"] = "excellent"
    fixture.write_run(df)
    with pytest.raises(JudgmentLanguageError, match="excellent"):
        generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)


def test_output_is_deterministic_for_the_same_input(fixture):
    fixture.write_run(_arima_rows())
    text1 = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    text2 = generate_factsheet("AAPL", "arima", fixture.run_log, fixture.storage)
    assert text1 == text2


def test_write_factsheet_writes_to_the_real_data_root_layout(fixture):
    fixture.write_run(_arima_rows())
    path = write_factsheet(fixture.tmp, "AAPL", "arima", fixture.run_log, fixture.storage)
    assert path == Path(fixture.tmp) / "factsheets" / "AAPL" / "arima.md"
    assert path.is_file()
    assert "hit_rate" in path.read_text(encoding="utf-8")


def test_write_summary_combines_angles_in_fixed_order_not_skipping_unrun_ones(fixture):
    fixture.write_run(_arima_rows())
    path = write_summary(fixture.tmp, "AAPL", fixture.run_log, fixture.storage, angle_names=["arima", "kalman_filters"])
    assert path == Path(fixture.tmp) / "factsheets" / "AAPL" / "_summary.md"
    text = path.read_text(encoding="utf-8")
    assert "arima" in text
    assert "kalman_filters" in text
    assert "no completed real run found yet" in text
