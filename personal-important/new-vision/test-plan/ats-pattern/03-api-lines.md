# ATS Pattern — API Lines (copy, not invent)

> Health open, protected needs `Authorization: Bearer <key>`. Key from `cat ./secrets/vinu_api_key` (also `vinu_infra/auth.py:29`). `host.docker.internal:8009` for LLM, not `127.0.0.1` inside container.

| Check | Curl line | Expected |
|---|---|---|
| health open | `curl http://localhost:8083/analysis/health` (swap `8080/news`, `8081/stock`, `8082/features`, `8084/strategy`, `8086/agent`, `8087/research`, `8090/portfolio`, `8091/live`) | `200` with or without Bearer |
| protected no header | `curl -i http://localhost:8086/agent/broker/performance/test` | `401 Unauthorized` (file→container wiring ok, `VINU_API_KEY` set) |
| protected bad key | `curl -i -H "Authorization: Bearer wrong-key" http://localhost:8086/agent/broker/performance/test` | `403 Forbidden` |
| protected good key | `KEY=$(cat ./secrets/vinu_api_key)`<br/>`curl -i -H "Authorization: Bearer $KEY" http://localhost:8086/agent/broker/performance/test` | `404/200` not `401/403` (key accepted) |
| stock price | `curl -H "Authorization: Bearer $KEY" "http://localhost:8081/stock/candles/AAPL?interval=1d&days=5&adjusted=true"` | `200` `data` array with `close` |
| features | `curl -H "Authorization: Bearer $KEY" http://localhost:8082/features/AAPL` | `200` with `data`/`features` + `rsi_14` etc. |
| research sweep | `curl -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" http://localhost:8087/research/sweep/candidate -d '{"symbol":"AAPL","recipe":"crossover","params":{"fast_period":10,"slow_period":30},"from_date":"2026-03-01","to_date":"2026-09-07"}'` | `200` `run_id` + `metrics` (dates required; param names must match `GET /research/sweep/recipes`, e.g. `fast_period` not `fast`) |
| portfolio state | `curl -H "Authorization: Bearer $KEY" http://localhost:8090/portfolio/state` | `200` `weights` + `correlation_matrix` + `composition_view` (`_check_composition_gaps`) |
| live account | `curl -H "Authorization: Bearer $KEY" http://localhost:8091/live/health` + `curl -H "Authorization: Bearer $KEY" http://localhost:8086/agent/broker/account` | `200` |
| freeze lineage | `python3 -c "from vinu_infra.freeze import freeze_manifest; freeze_manifest('freeze.json'); print(open('freeze.json').read()[:800])"` | `freeze.json` with `env` + `data_roots` + `file_hashes` |

Swap `AAPL` for `MSFT`/`NVDA` for 3-ticker ATS; swap `8086/agent` for `8090/portfolio` etc. per `requirements.md` table — don't invent new prefix.

## LLM reachability (containers → host)

```bash
# Inside agent-api container, host.docker.internal must resolve (docker-compose.yml:38 extra_hosts)
docker compose exec agent-api python3 -c "import urllib.request; urllib.request.urlopen('http://host.docker.internal:8009/v1/models', timeout=5); print('llm reachable')"
```
