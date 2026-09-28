import json
import logging
import time

from ..agent.tools import BaseTool
from ._call_cache import CallCache

LOG = logging.getLogger(__name__)

# item #11 finding #3 / item #19 finding #4: yfinance is flaky (the same
# vendor-flakiness pattern flagged in both audits, for two independent
# callers). A retry-after-sleep loop, same convention
# allocation_tool.py's own retry already uses -- not vinu_infra.retry's
# HTTP helper, whose exceptions= tuple is requests-specific and wouldn't
# reliably match yfinance's own transient failure modes.
_FETCH_RETRIES = 3
_RETRY_SLEEP_SEC = 1.0


class FundamentalsTool(BaseTool):
    name = "get_fundamentals"
    description = "Fetch fundamental data for a symbol: financial ratios, income statement summary, balance sheet, and valuation metrics"
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol (e.g., AAPL)"},
            "metric": {
                "type": "string",
                "description": "Metric type: summary, income, balance, cashflow, ratios, all (default: summary)",
                "enum": ["summary", "income", "balance", "cashflow", "ratios", "all"],
            },
        },
        "required": ["symbol"],
    }
    is_readonly = True

    def __init__(self):
        self._cache = CallCache()

    def execute(self, **kwargs) -> str:
        import yfinance as yf

        symbol = kwargs["symbol"].upper()
        metric = kwargs.get("metric", "summary")

        cache_key = (symbol, metric)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        ticker = None
        info: dict = {}
        last_exc: Exception | None = None
        for attempt in range(1, _FETCH_RETRIES + 1):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info or {}
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < _FETCH_RETRIES:
                    LOG.warning(
                        "get_fundamentals(%s) attempt %d/%d failed, retrying after %.1fs: %s",
                        symbol, attempt, _FETCH_RETRIES, _RETRY_SLEEP_SEC, exc,
                    )
                    time.sleep(_RETRY_SLEEP_SEC)
        if last_exc is not None:
            return json.dumps({"status": "error", "error": str(last_exc)})

        if not info or not info.get("symbol"):
            return json.dumps({"status": "error", "error": f"Symbol {symbol} not found"})

        result = {"symbol": symbol, "name": info.get("longName", info.get("shortName", ""))}

        if metric in ("summary", "all"):
            result["summary"] = {
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "ev_to_ebitda": info.get("enterpriseToEbitda"),
                "ev_to_revenue": info.get("enterpriseToRevenue"),
                "dividend_yield": info.get("dividendYield"),
                "payout_ratio": info.get("payoutRatio"),
                "beta": info.get("beta"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            }

        if metric in ("income", "all"):
            try:
                inc = ticker.financials
                if inc is not None and not inc.empty:
                    result["income_statement"] = inc.to_dict()
            except Exception:
                pass

        if metric in ("balance", "all"):
            try:
                bs = ticker.balance_sheet
                if bs is not None and not bs.empty:
                    result["balance_sheet"] = bs.to_dict()
            except Exception:
                pass

        if metric in ("cashflow", "all"):
            try:
                cf = ticker.cashflow
                if cf is not None and not cf.empty:
                    result["cash_flow"] = cf.to_dict()
            except Exception:
                pass

        if metric in ("ratios", "all"):
            result["ratios"] = {
                "profit_margins": info.get("profitMargins"),
                "operating_margins": info.get("operatingMargins"),
                "return_on_equity": info.get("returnOnEquity"),
                "return_on_assets": info.get("returnOnAssets"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "quick_ratio": info.get("quickRatio"),
                "free_cashflow": info.get("freeCashflow"),
                "operating_cashflow": info.get("operatingCashflow"),
                "earnings_per_share": info.get("trailingEps"),
                "forward_eps": info.get("forwardEps"),
                "book_value": info.get("bookValue"),
            }

        out = json.dumps({k: v for k, v in result.items() if v is not None}, indent=2, default=str)
        self._cache.set(cache_key, out)
        return out
