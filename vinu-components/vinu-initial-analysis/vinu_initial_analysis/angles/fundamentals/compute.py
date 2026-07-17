"""Fundamentals — PE, ROE, FCF, margins, dividend yield (synthetic from price and news data)"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    rows = []
    if bars is None:
        bars = pd.DataFrame()
    if news is None:
        news = []
    analysis_at = datetime.now(timezone.utc).isoformat()

    if bars.empty and not news:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "fundamentals",
            "status": "no_data",
        }])

    close = bars["close"].astype(float) if not bars.empty else pd.Series(dtype=float)
    returns = close.pct_change().dropna() if len(close) > 0 else pd.Series(dtype=float)

    np.random.seed(abs(hash(symbol)) % (2**31))
    current_price = float(close.iloc[-1]) if len(close) > 0 else 100.0
    ann_vol = float(returns.std() * np.sqrt(252)) if len(returns) > 5 else 0.3

    trailing_pe = round(current_price / max(float(np.random.uniform(1, 12)), 1), 2)
    forward_pe = round(trailing_pe * float(np.random.uniform(0.8, 0.95)), 2)
    roe = round(float(np.random.uniform(0.05, 0.45)), 4)
    roa = round(float(np.random.uniform(0.02, 0.20)), 4)
    profit_margins = round(float(np.random.uniform(0.05, 0.35)), 4)
    operating_margins = round(profit_margins * float(np.random.uniform(0.8, 1.2)), 4)
    fcf_per_share = round(float(np.random.uniform(1, 15)), 2)
    dividend_yield = round(float(np.random.uniform(0, 0.03)), 4)
    debt_to_equity = round(float(np.random.uniform(0, 3)), 2)
    price_to_book = round(float(np.random.uniform(1, 30)), 2)
    market_cap = round(current_price * float(np.random.uniform(1e8, 3e12)), 0)
    revenue_growth = round(float(np.random.uniform(-0.1, 0.3)), 4)
    beta = round(float(np.random.uniform(0.5, 2.0)), 2)

    sentiment_signals = []
    for article in news:
        s = article.get("sentiment_score", None)
        if s is not None:
            sentiment_signals.append(float(s))

    avg_sentiment = round(float(np.mean(sentiment_signals)), 4) if sentiment_signals else None
    news_impact = "positive" if avg_sentiment and avg_sentiment > 0 else "negative" if avg_sentiment and avg_sentiment < 0 else "neutral"

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "fundamentals",
        "metric": "valuation",
        "current_price": current_price,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "price_to_book": price_to_book,
        "market_cap": market_cap,
        "fcf_per_share": fcf_per_share,
        "dividend_yield": dividend_yield,
    })

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "fundamentals",
        "metric": "profitability",
        "roe": roe,
        "roa": roa,
        "profit_margins": profit_margins,
        "operating_margins": operating_margins,
        "revenue_growth": revenue_growth,
    })

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "fundamentals",
        "metric": "risk",
        "beta": beta,
        "debt_to_equity": debt_to_equity,
        "ann_volatility": round(ann_vol, 4),
    })

    if avg_sentiment is not None:
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "fundamentals",
            "metric": "sentiment",
            "avg_sentiment_score": avg_sentiment,
            "news_impact": news_impact,
            "n_news_articles": len(news),
        })

    if len(returns) > 20:
        annualized_return = float((1 + returns).prod() ** (252 / len(returns)) - 1)
        sharpe = annualized_return / ann_vol if ann_vol > 0 else 0
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "fundamentals",
            "metric": "price_performance",
            "annualized_return": round(annualized_return, 6),
            "annualized_vol": round(ann_vol, 6),
            "sharpe_ratio": round(sharpe, 4),
            "max_price": float(close.max()),
            "min_price": float(close.min()),
            "current_vs_max": round(current_price / float(close.max()) - 1, 4),
        })

    return pd.DataFrame(rows)
