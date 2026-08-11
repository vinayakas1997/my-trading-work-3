# LLM call evidence — AAPL pipeline window (2026-08-11)

## vinu-news step (AAPL pipeline, window >= 15:22:55Z)
From `/data/llm_calls.jsonl` in news-api:

- total calls in window: **19,503**
- success: 86 | failed: 19,417
- failure breakdown: 19,416 × HTTP 429, 1 × 503
- pipeline client counter (run report): 206 calls, 192 failed (191×429 + 1×503), 14 success
- step error: `HTTPConnectionPool(host='127.0.0.1', port=8080): Read timed out. (read timeout=30)`
- server-side analysis continued after client disconnect; news_analysis table = 928 rows

## vinu-research (research run id 3, 76.73s)
- all in-run gemma calls: HTTP 429, retried 3× with 1s/2s/4s backoff, then fail-closed
- loop completed degraded: 1 iteration, strategy code generated (SMA crossover), validation verdict STOP
  - trade-permutation p-value: insufficient data (skipped)
  - bootstrap Sharpe CI lower 0.0 <= 0 (FAIL)
  - price-path resample p-value 0.6310 >= 0.1 (FAIL)
  - walk-forward consistency 0.20 < 0.60 (FAIL)

## vinu-agent (session 686b070db934)
- assistant reply = OpenRouter 429 error surfaced as message:
  `free-models-per-day-high-balance`, X-RateLimit-Limit 1000, X-RateLimit-Remaining 0,
  limit_source openrouter_free_tier_daily, remedy hint "wait for daily reset or purchase credits"
