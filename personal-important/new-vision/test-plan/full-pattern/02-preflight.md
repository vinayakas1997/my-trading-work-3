# Full Pattern — Preflight (full window + lineage)

> Same as ATS `02-preflight` but with `2022-01-01` origin and lineage.

```bash
# 1. Flip to full origin (must be BEFORE current quarter 2026-07-01, but now far before — fine)
grep VINU_STAGE1_START_DATE .env  # expect 2022-01-01 (not 2026-03-01)
# if still short, edit .env VINU_STAGE1_START_DATE=2022-01-01 then:
docker compose up -d --force-recreate initial-analysis-api  # tier2 recomputes 12/period

# 2. Same secrets + healthy + auth lines as ats-pattern/02-preflight.md (scripts/setup-secrets.sh --check, docker compose ps healthy, curl 401/403/200 per requirements.md)

# 3. Freeze baseline for lineage (B21)
python3 -c "from vinu_infra.freeze import freeze_manifest; freeze_manifest('freeze-baseline.json'); print('baseline', open('freeze-baseline.json').read()[:300])"
# after full run, freeze again and diff:
python3 -c "from vinu_infra.freeze import freeze_manifest, contamination_check; import json; b=json.load(open('freeze-baseline.json')); n=freeze_manifest(); print(contamination_check(b,n))"

# 4. Watchlist still AAPL,MSFT,NVDA but now full history — expect slower first analysis run, then Gate advances.
```
