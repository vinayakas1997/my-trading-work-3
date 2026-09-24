import json
from pathlib import Path

import pytest

from vinu_agent.storage.ticker_summaries import TickerSummaryStore
from vinu_agent.tools.book_gatekeeper_tool import AskTickerBookTool


@pytest.fixture
def store(tmp_path: Path) -> TickerSummaryStore:
    return TickerSummaryStore(tmp_path / "summaries.db")


def _tool(store=None) -> AskTickerBookTool:
    tool = AskTickerBookTool()
    tool._ticker_summary_store = store
    return tool


def _ask(tool: AskTickerBookTool, **kwargs) -> dict:
    return json.loads(tool.execute(**kwargs))


def _seed_full(store: TickerSummaryStore) -> None:
    store.upsert_summary(
        "AAPL", "summary text",
        source_run_id="run_aapl_1",
        angle_digest={"arima": {"forecast_price": 187.42}, "garch": {"forecast_volatility": 0.02}},
        cluster_digest={"A": "arima leans up.", "C": "volatility calm."},
        cluster_anomalies={"C": ["garch NaN at 1H"]},
        cross_cluster={"corroborations": ["A", "B"]},
    )


class TestIndex:
    def test_needs_no_ticker_or_store(self) -> None:
        result = _ask(_tool(), chapter="index")
        assert set(result["chapters"]) == {"angles", "experience"}
        assert result["chapters"]["experience"]["available"] is False
        assert result["cluster_index"]["A"]["title"] == "Classical statistical forecasts"


class TestAnglesChapter:
    def test_full_row_returns_all_four_sub_chapters_available(self, store) -> None:
        _seed_full(store)
        result = _ask(_tool(store), chapter="angles", ticker="aapl")

        assert result["ticker"] == "AAPL"
        assert result["source_run_id"] == "run_aapl_1"
        assert result["updated_at"]
        for sub in ("glossary", "per_ticker", "clusters", "cross_cluster"):
            assert result[sub]["available"] is True, sub

    def test_clusters_are_labeled_with_real_titles_not_bare_letters(self, store) -> None:
        _seed_full(store)
        clusters = _ask(_tool(store), chapter="angles", ticker="AAPL", sub="clusters")["clusters"]["data"]

        assert clusters["A"]["title"] == "Classical statistical forecasts"
        assert clusters["A"]["synthesis"] == "arima leans up."
        assert clusters["C"]["anomalies"] == ["garch NaN at 1H"]
        assert clusters["A"]["anomalies"] == []

    def test_cluster_param_narrows_to_one_letter(self, store) -> None:
        _seed_full(store)
        clusters = _ask(_tool(store), chapter="angles", ticker="AAPL", sub="clusters", cluster="c")["clusters"]["data"]
        assert set(clusters) == {"C"}

    def test_sub_param_returns_only_that_sub_chapter(self, store) -> None:
        _seed_full(store)
        result = _ask(_tool(store), chapter="angles", ticker="AAPL", sub="per_ticker")
        assert "per_ticker" in result
        assert not {"glossary", "clusters", "cross_cluster"} & set(result)

    def test_glossary_covers_only_angles_in_this_tickers_digest(self, store) -> None:
        _seed_full(store)
        glossary = _ask(_tool(store), chapter="angles", ticker="AAPL", sub="glossary")["glossary"]["data"]

        assert set(glossary) == {"arima", "garch"}
        assert glossary["arima"]["cluster"] == "A"
        assert glossary["garch"]["cluster_title"] == "Volatility & drawdown risk"
        assert glossary["arima"]["explanation"]

    def test_stale_row_reports_each_sub_chapter_independently(self, store) -> None:
        """A row whose comprehension predates cluster synthesis: angle
        data present, clusters never computed. 1c/1d must say
        'unavailable' with a reason, not return an empty dict that reads
        as 'checked, found nothing'."""
        store.upsert_summary("MSFT", "old summary", angle_digest={"arima": {"forecast_price": 412.1}})
        result = _ask(_tool(store), chapter="angles", ticker="MSFT")

        assert result["per_ticker"]["available"] is True
        assert result["glossary"]["available"] is True
        assert result["clusters"]["available"] is False
        assert result["clusters"]["reason"]
        assert result["cross_cluster"]["available"] is False


class TestFailOpen:
    def test_no_row_for_ticker(self, store) -> None:
        result = _ask(_tool(store), chapter="angles", ticker="MSFT")
        assert result == {"ticker": "MSFT", "available": False, "reason": "no comprehension row for this ticker yet"}

    def test_no_store_configured(self) -> None:
        result = _ask(_tool(None), chapter="angles", ticker="AAPL")
        assert result["available"] is False

    def test_store_read_failure_does_not_raise(self) -> None:
        class _Broken:
            def get_summary(self, ticker):
                raise RuntimeError("db locked")

        result = _ask(_tool(_Broken()), chapter="angles", ticker="AAPL")
        assert result["available"] is False
        assert "db locked" in result["reason"]


class TestBadInput:
    @pytest.mark.parametrize("kwargs", [
        {"chapter": "nonsense"},
        {"chapter": "angles"},
        {"chapter": "angles", "ticker": "AAPL", "sub": "nonsense"},
        {"chapter": "angles", "ticker": "AAPL", "cluster": "Z"},
    ])
    def test_returns_error_not_raise(self, store, kwargs) -> None:
        assert "error" in _ask(_tool(store), **kwargs)


def test_experience_chapter_is_an_honest_empty_slot() -> None:
    result = _ask(_tool(), chapter="experience")
    assert result["available"] is False
    assert "recording-the-experiece" in result["reason"]


def test_discovered_by_build_registry_with_store_injected(store) -> None:
    from vinu_agent.tools import build_registry

    registry = build_registry(ticker_summary_store=store)
    tool = registry.get("ask_ticker_book")
    assert tool is not None
    assert tool._ticker_summary_store is store
