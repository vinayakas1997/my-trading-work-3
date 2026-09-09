# ATS Pattern — Preflight (before any stage)

> Run in `vinu-components/`. Every service bound `127.0.0.1` only.

```bash
# 1. Secrets (must print "secret files ready")
scripts/setup-secrets.sh --check
# if FAILED, fill .env (ALPACA_API_KEY/SECRET rotated, VINU_LLM_API_KEY, VINU_API_KEY) then:
scripts/setup-secrets.sh

# 2. Up + healthy (not just running)
docker compose up -d
docker compose ps   # 9 healthy: news 8080, stock 8081, features 8082, analysis 8083, quant-core 8084, agent 8086, research 8087, portfolio 8090, live 8091
docker compose logs -f vinu-agent | grep -E "planner-worker|significance-worker|capital-allocator-worker|skill-audit-worker"
docker compose logs -f vinu-live  | grep -E "trade-plan-worker|feedback-worker|shadow-worker"

# 3. Auth gate (health open, rest Bearer) — proves file→container wiring
KEY=$(cat ./secrets/vinu_api_key)
curl -i http://localhost:8086/agent/broker/performance/test
# expect 401 (no header)
curl -i -H "Authorization: Bearer wrong-key" http://localhost:8086/agent/broker/performance/test
# expect 403 (bad value)
curl -i -H "Authorization: Bearer $KEY" http://localhost:8086/agent/broker/performance/test
# expect 404/200 not 401/403 (key accepted) — same pattern swap port/prefix per requirements.md

# 4. Start date for ATS (short, must be BEFORE 2026-07-01 Q3 or tier2 no_data)
grep VINU_STAGE1_START_DATE .env  # expect 2026-03-01 (6mo) or 2026-06-01 (3mo)
grep VINU_AGENT_WATCHLIST_SEED_TICKERS .env  # expect AAPL,MSFT,NVDA (3 for ATS)
```
