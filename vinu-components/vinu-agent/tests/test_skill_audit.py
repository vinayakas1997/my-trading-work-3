"""Tests for the skill-edit audit log -- Phase 6 (New-talk-agents/
new-thinking/new-restructure/phases/phase-6-thesis-intake/). See
agent/skill_audit.py.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.agent.skill_audit import SkillAuditStore, check_skill_edits


@pytest.fixture
def audit_store():
    path = Path(tempfile.mktemp(suffix=".db"))
    store = SkillAuditStore(path)
    yield store
    store.close()
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    risk_dir = tmp_path / "thesis-intake-risk-rules"
    risk_dir.mkdir()
    (risk_dir / "SKILL.md").write_text("---\nname: thesis-intake-risk-rules\n---\n\nline1\nline2\n", encoding="utf-8")

    strategy_dir = tmp_path / "thesis-intake-strategy-definitions"
    strategy_dir.mkdir()
    (strategy_dir / "SKILL.md").write_text("---\nname: thesis-intake-strategy-definitions\n---\n\nsome content\n", encoding="utf-8")

    return tmp_path


class TestCheckSkillEdits:
    def test_first_check_records_baseline_not_an_edit(self, skills_root, audit_store) -> None:
        entries = check_skill_edits(skills_root, audit_store)
        assert len(entries) == 1
        assert entries[0].diff_summary.startswith("baseline recorded")

    def test_no_change_records_nothing_on_second_check(self, skills_root, audit_store) -> None:
        check_skill_edits(skills_root, audit_store)
        entries = check_skill_edits(skills_root, audit_store)
        assert entries == []

    def test_risk_rules_edit_is_recorded(self, skills_root, audit_store) -> None:
        check_skill_edits(skills_root, audit_store)  # baseline

        risk_md = skills_root / "thesis-intake-risk-rules" / "SKILL.md"
        risk_md.write_text(risk_md.read_text(encoding="utf-8") + "line3\nline4\n", encoding="utf-8")

        entries = check_skill_edits(skills_root, audit_store)
        assert len(entries) == 1
        assert entries[0].skill_path == "thesis-intake-risk-rules/SKILL.md"
        assert "+2" in entries[0].diff_summary

    def test_strategy_definitions_edit_never_appears_in_this_log(self, skills_root, audit_store) -> None:
        """The audit log is scoped specifically to risk-relevant content
        (03-test.md) -- an edit to strategy-definitions is never recorded,
        by construction (it's not in AUDITED_SKILL_PATHS at all)."""
        check_skill_edits(skills_root, audit_store)  # baseline

        strategy_md = skills_root / "thesis-intake-strategy-definitions" / "SKILL.md"
        strategy_md.write_text(strategy_md.read_text(encoding="utf-8") + "extra line\n", encoding="utf-8")

        entries = check_skill_edits(skills_root, audit_store)
        assert entries == []

        history = audit_store.get_history("thesis-intake-strategy-definitions/SKILL.md")
        assert history == []

    def test_history_returns_every_recorded_entry_in_order(self, skills_root, audit_store) -> None:
        check_skill_edits(skills_root, audit_store)  # baseline
        risk_md = skills_root / "thesis-intake-risk-rules" / "SKILL.md"
        risk_md.write_text(risk_md.read_text(encoding="utf-8") + "line3\n", encoding="utf-8")
        check_skill_edits(skills_root, audit_store)
        risk_md.write_text(risk_md.read_text(encoding="utf-8") + "line4\n", encoding="utf-8")
        check_skill_edits(skills_root, audit_store)

        history = audit_store.get_history("thesis-intake-risk-rules/SKILL.md")
        assert len(history) == 3  # baseline + 2 real edits
        assert history[0].diff_summary.startswith("baseline")

    def test_missing_path_is_skipped_not_fatal(self, tmp_path, audit_store) -> None:
        entries = check_skill_edits(tmp_path, audit_store)  # no thesis-intake-risk-rules dir at all
        assert entries == []
