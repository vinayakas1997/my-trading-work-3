"""Tests for analysis H, governance piece (skill-edit before/after)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_agent.agent.skill_audit import AUDITED_SKILL_PATHS, SkillAuditStore

from vinu_reflection.reflection import skill_edit_governance


@pytest.fixture
def data_root(tmp_path, monkeypatch) -> Path:
    research_root = tmp_path / "research"
    research_root.mkdir()
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))
    return tmp_path / "agent"


def _record(*, timestamp: float, actual_return_pct: float) -> None:
    import json

    row_path = skill_edit_governance._trade_score_calibration_history_path()
    row_path.parent.mkdir(parents=True, exist_ok=True)

    with row_path.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": timestamp,
                    "direction": "up",
                    "actual_return_pct": actual_return_pct,
                    "tier": "strong",
                    "total_score": 50.0,
                }
            )
            + "\n"
        )


class TestSkillEditGovernanceRun:
    def test_no_edits_returns_no_findings(self, data_root):
        SkillAuditStore(data_root / "skill_audit.db")
        assert skill_edit_governance.run({"vinu_agent": data_root}) == []

    def test_no_calibration_history_returns_no_findings(self, data_root):
        store = SkillAuditStore(data_root / "skill_audit.db")
        store.record(
            AUDITED_SKILL_PATHS[0], old_hash="a", new_hash="b",
            old_line_count=10, new_line_count=12, diff_summary="tightened threshold",
        )
        assert skill_edit_governance.run({"vinu_agent": data_root}) == []

    def test_win_rate_drop_after_edit_is_flagged(self, data_root):
        store = SkillAuditStore(data_root / "skill_audit.db")

        edit_ts = 1_700_000_000.0
        # Backdate the edit's detected_at directly in the DB so it lands
        # in the middle of the synthetic calibration history below.
        import time as time_mod

        entry = store.record(
            AUDITED_SKILL_PATHS[0], old_hash="a", new_hash="b",
            old_line_count=10, new_line_count=12, diff_summary="loosened threshold",
        )
        conn = store._get_conn()
        conn.execute(
            "UPDATE skill_edit_audit SET detected_at = ? WHERE entry_id = ?",
            (time_mod.strftime("%Y-%m-%dT%H:%M:%SZ", time_mod.gmtime(edit_ts)), entry.entry_id),
        )
        conn.commit()

        # 20 wins before the edit.
        for i in range(20):
            _record(timestamp=edit_ts - 1000 + i, actual_return_pct=5.0)
        # 20 losses after the edit.
        for i in range(20):
            _record(timestamp=edit_ts + 1000 + i, actual_return_pct=-5.0)

        findings = skill_edit_governance.run({"vinu_agent": data_root})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "system"
        assert finding.scope_key == "skill_rule_edits"
        assert finding.metric_name == "outcome_delta_before_after"
        assert finding.primary_metric == pytest.approx(-1.0)  # 0% win rate after vs 100% before
        assert finding.psi > 0.25
        assert finding.signal_json["skill_path"] == AUDITED_SKILL_PATHS[0]

    def test_below_window_minimum_is_skipped(self, data_root):
        store = SkillAuditStore(data_root / "skill_audit.db")
        store.record(
            AUDITED_SKILL_PATHS[0], old_hash="a", new_hash="b",
            old_line_count=10, new_line_count=12, diff_summary="x",
        )
        for i in range(5):
            _record(timestamp=1_700_000_000.0 + i, actual_return_pct=1.0)

        assert skill_edit_governance.run({"vinu_agent": data_root}) == []
