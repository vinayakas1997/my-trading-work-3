"""v1 C4 of the-inconsistencies-v2 (plan item 2.4d), portfolio half.

`AllocationHistoryStore` persisted every daily allocation, including which
candidates were left unfunded and why (`not_funded`), and had readers -- but no
HTTP route anywhere, so "why is this weight 0" could not be answered without
opening the database file. `GET /portfolio/allocation-history` and
`GET /portfolio/not-funded` are those routes (read-only).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from vinu_portfolio.config import PortfolioConfig
from vinu_portfolio.server.app import create_app
from vinu_portfolio.service import PortfolioService


@pytest.fixture
def svc(tmp_path):
    s = PortfolioService(config=PortfolioConfig(data_root=tmp_path))
    yield s
    # the store is closed by the service's own close path in production; tests just drop it


def _record(svc, date, *, n_weights=2, not_funded=None, equity=100_000.0, deployable=90_000.0):
    svc._allocation_history.record_daily_allocation(
        allocation_date=date,
        weights=[{"name": f"s{i}", "target_weight": 0.1} for i in range(n_weights)],
        account_equity=equity, deployable_equity=deployable,
        not_funded=not_funded,
    )


_NF = {
    "kind": "portfolio_strategy", "identifier": "weak_strat", "stage": "daily_allocation",
    "rejection_category": "regime_alignment", "rejection_detail": "smallest tilt was regime_alignment=0.0000",
}


# ------------------------------------------------------------------ service

def test_summaries_are_newest_first_with_counts_and_a_limit(svc):
    _record(svc, "2026-09-28", n_weights=3, not_funded=[_NF])
    _record(svc, "2026-09-29", n_weights=2)
    _record(svc, "2026-09-30", n_weights=4, not_funded=[_NF, _NF])
    rows = svc.allocation_history_summaries()
    assert [r["allocation_date"] for r in rows] == ["2026-09-30", "2026-09-29", "2026-09-28"]
    assert [(r["n_weights"], r["n_not_funded"]) for r in rows] == [(4, 2), (2, 0), (3, 1)]
    assert rows[0]["deployable_equity"] == 90_000.0 and rows[0]["account_equity"] == 100_000.0
    assert [r["allocation_date"] for r in svc.allocation_history_summaries(limit=1)] == ["2026-09-30"]
    assert svc.allocation_history_summaries(limit=0) == []


def test_latest_not_funded_is_none_when_nothing_was_ever_recorded(svc):
    assert svc.latest_not_funded() is None
    assert svc.allocation_history_summaries() == []


def test_latest_not_funded_returns_the_newest_allocations_entries_with_reasons(svc):
    _record(svc, "2026-09-29", not_funded=[{**_NF, "identifier": "old"}])
    _record(svc, "2026-09-30", not_funded=[_NF])
    got = svc.latest_not_funded()
    assert got["allocation_date"] == "2026-09-30" and got["count"] == 1
    assert got["not_funded"][0]["identifier"] == "weak_strat"
    assert "regime_alignment" in got["not_funded"][0]["rejection_detail"]


def test_an_allocation_that_funded_everything_is_distinct_from_no_allocation(svc):
    _record(svc, "2026-09-30", not_funded=[])
    got = svc.latest_not_funded()
    assert got is not None and got["count"] == 0 and got["not_funded"] == []


# ------------------------------------------------------------------ routes

@pytest.fixture
def client(tmp_path):
    real = PortfolioService(config=PortfolioConfig(data_root=tmp_path))
    with patch("vinu_portfolio.server.app.PortfolioService", return_value=real):
        yield TestClient(create_app()), real


def test_not_funded_route_says_none_before_any_allocation(client):
    c, _ = client
    assert c.get("/portfolio/not-funded").json() == {"status": "none", "count": 0, "not_funded": []}
    assert c.get("/portfolio/allocation-history").json() == {"count": 0, "allocations": []}


def test_routes_return_what_was_recorded(client):
    c, real = client
    _record(real, "2026-09-30", n_weights=3, not_funded=[_NF])
    nf = c.get("/portfolio/not-funded").json()
    assert nf["status"] == "ok" and nf["count"] == 1 and nf["allocation_date"] == "2026-09-30"
    assert nf["not_funded"][0]["identifier"] == "weak_strat"
    hist = c.get("/portfolio/allocation-history?limit=5").json()
    assert hist["count"] == 1 and hist["allocations"][0]["n_not_funded"] == 1


def test_new_routes_do_not_shadow_existing_ones(client):
    c, _ = client
    assert c.get("/portfolio/health").json()["status"] == "ok"
