import json
import time
import urllib.request

ENDPOINT = "http://localhost:8092/v1/chat/completions"
MODEL = "qwen3.5-4b-q4_k_m-local"

# Adapted, single-shot version of the real angle_synthesizer/prompt.md
# (verbatim rules + the real 7-cluster scheme from manager_prompt.md /
# 00-explanation.md), minus the tool-calling steps (explain_angle,
# compare_angles, find_trade_plan_artifact) since this is a direct
# chat_json-style call, not run through the actual vinu-agent harness.
# Flagged explicitly as an adaptation, not a byte-for-byte reuse.
SYSTEM_PROMPT = (
    "You are the Angle Synthesizer, a specialist reviewing all 28 vinu-initial-analysis "
    "angles for one ticker, each with data at multiple real timeframes (1min/5min/15min/"
    "1H/4H/1D and for some angles also 1W/1M/6M). "
    "Rules: Only treat an angle+timeframe as informative if it has real data -- if an angle "
    "has row_count=0 or an 'error' field, say so plainly, don't guess at what it might show. "
    "Cite specific numbers from angles that do have data. Never invent a number, trend, or "
    "signal that isn't actually in the returned data. "
    "Organize angles with real data into these 7 fixed clusters: "
    "A -- Classical statistical forecasts: arima, exponential_smoothing, kalman_filters. "
    "B -- Deep-learning / foundation-model forecasts: chronos, dlinear, itransformer, kronos, "
    "lag_llama, lpatchtst, lstm, moirai, moment, patchtst, tft, timer_timerxl, timesfm, "
    "tips_regime_aware_transformer. "
    "C -- Volatility & drawdown risk: garch, drawdown_deep_dive. "
    "D -- Regime & trend structure: regime_analysis, trend_lifecycle, trend_session_structure. "
    "E -- Shock / personality behavior: shock_clustering, shock_personality. "
    "F -- Cross-asset & causality: peer_relative_strength, news_price_causality. "
    "G -- Validation & attribution: backtesting_44_metrics, pnl_attribution. "
    "For each cluster with data, write one short synthesis sentence. For Cluster B "
    "specifically (14 members), report a real consensus rate (e.g. '4 of 5 models with data "
    "lean up'), not 14 individual descriptions. "
    "You also have real per-timeframe data for many angles -- use it: note whether the "
    "signal is consistent across timeframes or diverges (e.g. bullish daily but weakening "
    "intraday), since that's real information a single-timeframe read would miss. "
    "Flag anything that looks malformed (a NaN-like value, an impossible range) or stale "
    "(inconsistent with the angle's other timeframes) rather than treating it as normal. "
    "Return your synthesis as prose covering: (1) how many of the 28 angles have real data "
    "at any timeframe, (2) per-cluster synthesis sentences noting any real cross-timeframe "
    "divergence, (3) anything anomalous/malformed/missing you noticed and how you handled it, "
    "(4) what you'd check next before trusting this. Then end with a fenced ```json block: "
    '{"cluster_digest": {"A": "...", "B": "...", ...}, "anomalies_found": ["..."]}. '
    "Only include clusters that had at least one angle with real data."
)

with open("clean_digest.txt", encoding="utf-8") as f:
    clean_digest = f.read()
with open("uneven_digest.txt", encoding="utf-8") as f:
    uneven_digest = f.read()

RUNS = {
    "clean": f"Ticker: AAPL\n\n=== Angle Digest (all real timeframes per angle) ===\n{clean_digest}",
    "uneven": f"Ticker: AAPL\n\n=== Angle Digest (all real timeframes per angle) ===\n{uneven_digest}",
}

results = {}
for name, user_prompt in RUNS.items():
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 6000,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=400) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - start
    results[name] = {"body": body, "elapsed_sec": elapsed, "prompt_chars": len(user_prompt)}
    print(f"=== {name} done in {elapsed:.1f}s (prompt {len(user_prompt)} chars) ===")
    msg = body["choices"][0]["message"]
    print("finish_reason:", body["choices"][0].get("finish_reason"))
    print("content:\n", msg.get("content"))
    print()

with open("full_book_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
