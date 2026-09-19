"""Tests for analysis T (LESSON snapshots vs. MaturityAssessor)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vinu_research.models import Artifact, CalibrationEntry

from vinu_reflection.reflection import lesson_maturity_baseline_check as t
from vinu_reflection.reflection import _maturity_assessor as ma
from vinu_agent.broker.performance_store import PaperPerformanceStore
from vinu_infra.reflection import ReflectionStore, write_findings


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def performance_store(data_root) -> PaperPerformanceStore:
    return PaperPerformanceStore(data_root / "paper_performance.db")


@pytest.fixture
def strategy_store(tmp_path, monkeypatch):
    research_root = tmp_path / "research"
    research_root.mkdir()
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))
    return ma.get_strategy_store()


def _write_lesson(data_root: Path, *, closed: int, last5: str, ts: str = "20260920_120000") -> None:
    lessons_dir = data_root / "live" / "lessons"
    lessons_dir.mkdir(parents=True, exist_ok=True)
    lesson = {
        "closed": closed,
        "fills": closed,
        "avg_commission": 0.01,
        "last5": last5,
        "halted": False,
        "at": "2026-09-20T12:00:00+00:00",
    }
    (lessons_dir / f"LESSON_{ts}.json").write_text(json.dumps(lesson), encoding="utf-8")


def _add_recent_form(strategy_store, outcomes: list[bool]) -> None:
    strategy_store.upsert_artifact(
        Artifact(artifact_id="art_1", type="trade_plan", name="art_1", universe=["AAPL"])
    )
    for i, correct in enumerate(outcomes):
        strategy_store.append_calibration_entry(
            CalibrationEntry(
                artifact_id="art_1",
                forecast_direction="long",
                actual_return_pct=0.02 if correct else -0.02,
                directional_correct=correct,
                timestamp=f"2026-09-{i + 1:02d}T00:00:00",
            )
        )


def _roots(data_root: Path) -> dict[str, Path]:
    return {"vinu_agent": data_root, "vinu_live": data_root / "live"}


class TestLessonMaturityBaselineCheck:
    def test_no_lesson_file_returns_no_findings(self, performance_store, strategy_store, data_root):
        assert t.run(_roots(data_root)) == []

    def test_lesson_exists_but_no_calibration_evidence_returns_no_findings(
        self, performance_store, strategy_store, data_root
    ):
        _write_lesson(data_root, closed=30, last5="WWWWW")
        assert t.run(_roots(data_root)) == []

    def test_agreement_when_both_improving(self, performance_store, strategy_store, data_root):
        _write_lesson(data_root, closed=30, last5="WWWLL")  # 3W/2L -> improving
        _add_recent_form(strategy_store, [False, False, True, True, True])  # improving

        findings = t.run(_roots(data_root))
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "system"
        assert finding.scope_key == "lesson_baseline_check"
        assert finding.signal_json["agree"] is True
        assert finding.domain_floor_breached is False
        assert finding.primary_metric == 1.0

    def test_disagreement_when_lesson_improving_but_assessor_degrading(
        self, performance_store, strategy_store, data_root
    ):
        _write_lesson(data_root, closed=30, last5="WWWLL")  # improving
        _add_recent_form(strategy_store, [True, True, False, False, False])  # degrading

        findings = t.run(_roots(data_root))
        assert len(findings) == 1
        finding = findings[0]
        assert finding.signal_json["lesson_reading"] == "improving"
        assert finding.signal_json["maturity_reading"] == "degrading"
        assert finding.signal_json["agree"] is False
        assert finding.domain_floor_breached is True
        assert finding.primary_metric == 0.0

    def test_flat_lesson_reading_never_counts_as_disagreement(
        self, performance_store, strategy_store, data_root
    ):
        _write_lesson(data_root, closed=30, last5="WWLL")  # 2W/2L -> flat
        _add_recent_form(strategy_store, [True, True, False, False, False])  # degrading

        findings = t.run(_roots(data_root))
        assert findings[0].signal_json["agree"] is True
        assert findings[0].domain_floor_breached is False

    def test_evidence_count_is_lesson_closed_count(self, performance_store, strategy_store, data_root):
        _write_lesson(data_root, closed=42, last5="WWWWW")
        _add_recent_form(strategy_store, [True] * 5)

        findings = t.run(_roots(data_root))
        assert findings[0].evidence_count == 42

    def test_most_recent_lesson_file_used(self, performance_store, strategy_store, data_root):
        _write_lesson(data_root, closed=30, last5="LLLLL", ts="20260901_000000")
        _write_lesson(data_root, closed=35, last5="WWWWW", ts="20260920_120000")
        _add_recent_form(strategy_store, [True] * 5)

        findings = t.run(_roots(data_root))
        assert findings[0].signal_json["lesson_reading"] == "improving"
        assert findings[0].evidence_count == 35


class TestLessonMaturityEndToEnd:
    def test_run_write_findings_round_trip(self, performance_store, strategy_store, data_root):
        # A routine "agree" finding (psi=0.0, domain_floor_breached=False)
        # correctly writes nothing at all -- same "most cycles produce
        # nothing" rule every other analyst follows (classify_severity()
        # treats it as routine). Only a real disagreement is significant
        # enough to actually get written, so that's what this round-trip
        # test needs to exercise.
        _write_lesson(data_root, closed=30, last5="WWWLL")  # improving
        _add_recent_form(strategy_store, [True, True, False, False, False])  # degrading

        reflection_store = ReflectionStore(data_root / "reflection.db")
        t.seed_reference_config(reflection_store)

        findings = t.run(_roots(data_root))
        written = write_findings(reflection_store, findings)
        assert len(written) == 1

        belief = reflection_store.get_belief(
            "lesson_maturity_baseline_check", "system", "lesson_baseline_check"
        )
        assert belief is not None
