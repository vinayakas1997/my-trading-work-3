from __future__ import annotations

from vinu_research.storage.models import (
    ResearchRunRecord,
    STATUS_DELETED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
)


def test_status_constants():
    assert STATUS_PENDING == "pending"
    assert STATUS_RUNNING == "running"
    assert STATUS_DONE == "done"
    assert STATUS_FAILED == "failed"
    assert STATUS_DELETED == "deleted"


def test_research_run_record_defaults():
    r = ResearchRunRecord(user_idea="test", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
    assert r.id is None
    assert r.status == STATUS_PENDING
    assert r.total_iterations == 0
    assert r.best_iteration == -1
    assert r.best_sharpe == 0.0
    assert r.best_max_dd == 0.0
    assert r.report_md == ""
    assert r.error_message is None
    assert r.created_at == ""
    assert r.updated_at == ""


def test_to_dict():
    r = ResearchRunRecord(
        id=42,
        user_idea="my idea",
        symbol="MSFT",
        from_date="2024-06-01",
        to_date="2024-08-31",
        status=STATUS_DONE,
        total_iterations=3,
        best_iteration=2,
        best_sharpe=1.25,
        best_max_dd=-0.08,
        report_md="# Report",
        error_message=None,
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-02T00:00:00",
    )
    d = r.to_dict()
    assert d["id"] == 42
    assert d["user_idea"] == "my idea"
    assert d["symbol"] == "MSFT"
    assert d["from_date"] == "2024-06-01"
    assert d["to_date"] == "2024-08-31"
    assert d["status"] == STATUS_DONE
    assert d["total_iterations"] == 3
    assert d["best_iteration"] == 2
    assert d["best_sharpe"] == 1.25
    assert d["best_max_dd"] == -0.08
    assert d["report_md"] == "# Report"
    assert d["error_message"] is None
    assert d["created_at"] == "2024-01-01T00:00:00"
    assert d["updated_at"] == "2024-01-02T00:00:00"
    assert len(d) == 14
