import json
import time
import urllib.request

from vinu_research.forecast_skill import _build_forecast_prompt, _FORECAST_SYSTEM_PROMPT

ENDPOINT = "http://localhost:8092/v1/chat/completions"
MODEL = "qwen3.5-9b-q4_k_m-local"

TRIALS = {
    "trial-01": dict(
        personality={"shock_clustering_score": 0.71, "regime_tag": "elevated_volatility", "correlation_to_spy_20d": 0.81},
        risk={"realized_vol_30d": 0.42, "atr_pct": 0.038, "max_drawdown_pct": -0.14, "drawdown_active": True,
              "momentum_20d_pct": -0.06, "sharpe_recent_20d": -0.35},
        summary_context={
            "summary": "AAPL is showing a strong bullish breakout above its 50-day moving average on unusually high volume (2.3x the 20-day average). Two sell-side analysts raised price targets this week citing strength in services revenue. Momentum indicators (patchtst, timesfm) both point to continued upside over the next 5-10 sessions. Sentiment angle (finbert) shows a marked improvement in news tone over the past 3 days.",
            "source_run_id": "run_20260921_0300", "angles_with_data": 9, "angle_count": 28,
            "angle_digest": {
                "patchtst": {"direction": "up", "confidence": 0.71},
                "timesfm": {"direction": "up", "confidence": 0.68},
                "finbert": {"sentiment_score": 0.62, "article_count": 14},
                "shock_personality": {"regime": "normal"},
                "shock_clustering": {"cluster_id": 2},
            },
            "cluster_digest": {
                "B": "patchtst leans up (confidence 0.71), timesfm leans up (confidence 0.68) -- 2 of 2 models with data lean up.",
                "E": "shock_personality regime=normal; shock_clustering cluster_id=2.",
            },
        },
    ),
    "trial-02": dict(
        personality={}, risk={},
        summary_context={
            "summary": "Very few angles have real data for NEWCO yet (1 of 28). The one angle with data (chronos) shows no clear directional signal. Confidence in this read is low given the limited coverage.",
            "source_run_id": "run_20260921_0300", "angles_with_data": 1, "angle_count": 28,
            "angle_digest": {"chronos": {"direction": "flat", "confidence": 0.1}},
            "cluster_digest": {"B": "chronos is flat, confidence 0.1 -- only 1 of 14 models has data this cycle."},
        },
        symbol="NEWCO",
    ),
    "trial-03": dict(
        personality={"shock_clustering_score": 15.0, "regime_tag": "", "correlation_to_spy_20d": 0.55},
        risk={"realized_vol_30d": "NaN", "atr_pct": -0.5, "max_drawdown_pct": 999.0, "drawdown_active": True,
              "momentum_20d_pct": 0.01, "sharpe_recent_20d": 0.4},
        summary_context={
            "summary": "Mixed signals across momentum and mean-reversion angles this cycle. No strong directional consensus.",
            "source_run_id": "run_20260921_0300", "angles_with_data": 14, "angle_count": 28,
            "angle_digest": {
                "patchtst": {"direction": "flat", "confidence": 0.34},
                "timesfm": {"direction": "down", "confidence": 0.29},
            },
            "cluster_digest": {
                "B": "patchtst is flat (confidence 0.34), timesfm leans down (confidence 0.29) -- mixed, low-confidence signals, 2 of 14 models with data.",
            },
        },
    ),
    "trial-05": dict(
        personality={"shock_clustering_score": 0.25, "regime_tag": "normal", "correlation_to_spy_20d": 0.62},
        risk={"realized_vol_30d": 0.19, "atr_pct": 0.015, "max_drawdown_pct": -0.02, "drawdown_active": False,
              "momentum_20d_pct": 0.03, "sharpe_recent_20d": 0.45},
        summary_context={
            "summary": "Constructive setup: momentum and trend angles both lean positive, sentiment has improved over the past week, no major red flags in the mean-reversion angles.",
            "source_run_id": "run_20260921_0300", "angles_with_data": 16, "angle_count": 28,
            "angle_digest": {
                "patchtst": {"direction": "up", "confidence": 0.58},
                "timesfm": {"direction": "up", "confidence": 0.55},
                "finbert": {"sentiment_score": 0.4},
                "shock_personality": {"regime": "normal"},
            },
            "cluster_digest": {
                "B": "patchtst leans up (confidence 0.58), timesfm leans up (confidence 0.55) -- 2 of 2 models with data lean up.",
                "E": "shock_personality regime=normal.",
            },
        },
        maturity_context={
            "tier": "cold_start", "n_real_trades": 0, "n_paper_trading_days": 3,
            "directional_accuracy": 0.0, "regime_coverage": None,
        },
    ),
}

results = {}
for name, cfg in TRIALS.items():
    symbol = cfg.get("symbol", "AAPL")
    prompt = _build_forecast_prompt(
        symbol, cfg["personality"], cfg["risk"],
        summary_context=cfg["summary_context"],
        maturity_context=cfg.get("maturity_context"),
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": _FORECAST_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 3000,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=200) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - start
    content = body["choices"][0]["message"].get("content", "")
    safe = content.encode("ascii", errors="replace").decode("ascii")
    print(f"=== {name} done in {elapsed:.1f}s, finish_reason={body['choices'][0].get('finish_reason')} ===")
    print(safe)
    print()
    results[name] = {"body": body, "elapsed_sec": elapsed, "prompt": prompt}
    with open("step6_remaining_trials_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
