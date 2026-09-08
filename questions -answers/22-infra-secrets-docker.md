# Infra Secrets Docker - 9 Services + GPU + Build (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `22`. Related: `18`.
Status: Infra step closed medium-small. Code steps ready to build next, no code changed yet in this doc.

---

## 9 services today (good)

Ports: news 8080, stock 8081, features 8082, initial 8083, quant-core 8084 (strategy + simulator), agent 8086, research 8087, portfolio 8090, live 8091. File `vinu-components/docker-compose.yml` services block.
Each `read_only: true` + tmpfs `/tmp`, `/home/app/.cache` + own `/data` bind. Agent extra `/nonexistent:rw,mode=1777,exec` fixed 06:51 restart loop. Same pattern as live entrypoint workers.
Depends healthy chain: stock + news -> features + initial -> quant-core + research -> portfolio + agent -> live. No start before healthy.
Healthchecks `python3 urllib` per service 10s interval 5s timeout 5 retries 15s start.

---

## Secrets today (good + warning kept)

Real secrets in `./secrets/` files gitignored, mounted `/run/secrets/<name>`. Read via `vinu_infra/secrets_loader`. Services list `vinu_api_key`, `alpaca`, `polygon`, `fmp`, `tushare`, `vinu_llm`, `telegram`, `discord`. File `docker-compose.yml:462` secrets block.
`env_file: .env` still present alongside secrets. `secrets_loader.py:44` fallback + warning `also present as plain env`. `docker inspect` leaks if `.env` filled. Decision `13-env-gap-decision.md` kept warning, not removed. I creditor: keep warning, remove plain values, fill secrets files only via `scripts/setup-secrets.sh`.
Ledger `inefficiencies-A-J.md:I` built warning check. Good.

---

## GPU + image + build today (good + slim planned)

Initial-analysis only GPU 1 nvidia, 8g 4cpu, `TRITON_CACHE_DIR /triton-cache` exec tmpfs. Rest CPU 1-2, 1-2g. Agent 2g 2cpu 512 pids.
Image 6.52GB torch + transformers + chronos + timesfm. Code 3.5MB. Deps 5GB. Discussed Q38-40 keep dynamic `data/models:/models:ro` + code bind, no weights in image. Slim CPU torch 3.5GB + warm host cache planned `18` step 4. Keep GPU kronos only.
Build 24min total: news 212s, stock 62s, rest small. ATS 0-9 14min without build. Full 2022 30min+ sweep. Timers fast `PLANNER 60 RISK 60 CAPITAL 90 SHADOW 90 TRADE 90` kept Full window, not 1800 default.

---

## Gaps + knobs for infra (medium-small)

1. `.env` plain leak risk. Fix: keep `.env-example` template committed, `.env` gitignored with non-secret URLs + intervals only, secrets files only for keys. Run `setup-secrets.sh --check` ready before up. Small docs + 1 check.
Knobs: `VINU_API_KEY` secret file, `ALPACA_*` secret files, `VINU_LLM_*` env URLs + model, `VINU_*_DATA_ROOT=/data` kept, `VINU_*_HOST/PORT` kept.
Status: Open docs. Small.

2. Restart + health flaps. Agent `/nonexistent` fixed mode 1777. Simulator circuit flap MSFT still open `02` file gap 5. Allocator fail-closed on portfolio down `allocation_tool.py:114`. Fix: retry 30 to 10s + 1s `inefficiencies-A-J.md:F` built pattern already for allocator, apply same to simulator + research HTTP. Small retry.
Knobs: `VINU_HTTP_RETRY_SEC=10`, `VINU_HTTP_RETRY_COUNT=3`.
Status: Open. Small.

3. Image slim + warm cache. Step `18` step 4. Slim CPU torch, warm `/models` host once, keep cache `/home/app/.cache`. GPU initial only. No code change, Dockerfile base + pip list. Medium infra. After trust green.
Status: Later. Saved here never lost.

---

## Order to build (docs + checks)

1. Secrets check + `.env` hygiene. 1 file script + docs. Do first.
2. Retry same pattern simulator + research. 1 timeout constant each. After 1 green.
3. Image slim warm cache. Last. Infra window.

After 1-3, infra done. Next is 23 runbooks. Different doc.

---

## All covered proof (nothing missed for infra)

- Compose services ports mounts caps health depends covered. Agent tmpfs fix 06:51 covered.
- Secrets block + loader warning + setup script covered. I built check kept.
- GPU reservations + triton cache + mem cpu pids covered. Image 6.52GB + slim plan `18` kept.
- Build 24min + ATS 14min + Full 30min + timers fast kept.
- 18 data PIT freeze pairlist kept. 16 broker throttle 10/sec kept. 15 monitor 90s kept.
