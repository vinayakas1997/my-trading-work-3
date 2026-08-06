---
name: e2e-check-round-2-tier2-fix-verification
status: complete
purpose: direct instructions for a Round 2 re-run of the small E2E check, scoped narrowly to verifying the tier2-staleness bug fix from Round 1. Read this after AGENTS.md, plan.md, and the Round 1 log in 03-vinu-initial-analysis.md — do not re-derive context, this file assumes you've read those.
---

# Round 2 — Verify the tier2 Staleness Fix

## Why this file exists

Round 1 of this E2E check (see `03-vinu-initial-analysis.md`'s
`BUGS-1`/`FIXES-1`) found and fixed a real bug: `vinu-initial-analysis`'s
continuous scheduler (`cli.py`'s `compute_main`, non-backfill branch)
called `runner.run(symbol)` with no time window every cycle. Because
`storage/meta.py`'s `has_existing_run()` treats `analysis_from=None,
analysis_until=None` as "no window filter," that call matched *any*
prior completed tier2 run for the symbol/angle forever — so the very
first tier2 run ever computed (752-753 daily obs, AAPL's ~$248
early-2025 regime) permanently blocked every later cycle from
recomputing, even though live `stock-api` data had grown to ~1150 daily
bars ending ~$311.97.

The fix (already applied, already in the codebase — **do not re-apply
it, just verify it**): `cli.py`'s continuous-mode call now passes an
explicit `[config.stage1_start_date, now]` window instead of `None,
None`, so the dedup check compares against the current window each
cycle and should actually recompute as time moves forward.

**This round's only job: prove that fix works against a real running
container, not just read the code and assume it does.** Round 1 already
covered `news-api`/`stock-api` and the rest of `vinu-initial-analysis`
(trigger→poll→tier3 flow, garch/vinu-tools check, model-mount check,
31-angle-count check) — none of that needs to be repeated here unless
something in this round makes you suspect it broke.

## Step-by-step

### 1. Rebuild and restart `initial-analysis-api` only

The fix is a code change (`vinu_initial_analysis/cli.py`), not an env
change, so this **does** need `--build`, unlike a plain `.env` edit:

```
cd vinu-components
docker compose up -d --build initial-analysis-api
```

Do not touch `news-api`/`stock-api` — nothing changed in either.

### 2. Confirm the fix landed inside the running container

```
docker exec vinu-components-initial-analysis-api-1 python3 -c \
  "import inspect; from vinu_initial_analysis import cli; print(inspect.getsource(cli.compute_main))" \
  | grep -A3 "stage1_start_date"
```

You should see the `start_ts = int(datetime.strptime(config.stage1_start_date, ...))`
block from the fix. If this doesn't show up, the container is running
stale code — rebuild didn't pick up the change; stop and investigate
before continuing (don't proceed to step 3 against unpatched code).

### 3. Record the pre-fix baseline (already have it — don't refetch, just reference it)

Round 1's frozen tier2 result for reference, so you can tell a genuinely
new run apart from the same stale one:
- `run_id` (whatever Round 1 logged, e.g. `503103784abd` per
  `03-vinu-initial-analysis.md` BUGS-1)
- 752-753 daily observations
- `last_close`/forecast anchored ~$248-251
- `analysis_from`/`analysis_until` timestamps from that run (check via
  `fetch` if not already recorded)

### 4. Let the continuous scheduler run at least one real cycle

`entrypoint.sh` starts `vinu-initial-compute --all --continuous &`.
Check its `--interval` (default 3600s / 1 hour unless overridden by an
env var — check `docker-compose.yml`'s `initial-analysis-api` block and
the container's actual env for an interval override). You need to wait
out at least one full interval from container start, or trigger it
faster if there's a way to shorten the interval for this check alone
(e.g. temporarily setting a shorter `--interval` via an env override,
**only for this verification run** — revert after, same spirit as the
temporary `VINU_STAGE1_START_DATE` override from Round 1's `plan.md`
step 2, don't leave a shortened interval in place for real use).

Watch the container logs for the scheduler actually attempting AAPL
again:

```
docker logs -f vinu-components-initial-analysis-api-1 | grep -i "analyzing\|skipping"
```

### 5. Fetch the tier2 result again and compare against the baseline

```
curl -s "http://localhost:8083/v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/<time-range>/arima" | python3 -m json.tool
```

(Use whatever `{time-range}` the tier2 fetch route actually expects —
check `03-vinu-initial-analysis.md`'s Round 1 notes or `routes_v1.py`
for the exact fetch shape, since tier2 fetch semantics were one of
Round 1's other findings.)

**What "fixed" looks like**: a new `run_id` (different from the Round 1
baseline), a growing observation count (should trend toward ~1150 as
`stock-api`'s series has grown), and `last_close`/forecast values in the
current ~$300s range instead of frozen at ~$248-251.

**What "still broken" looks like**: identical `run_id` to Round 1, same
752-753 obs, same ~$248 forecast — meaning either the fix didn't
actually change the dedup outcome, or the scheduler never got a chance
to run a full cycle in the time available. Distinguish between these two
failure modes before concluding the fix didn't work — check the
container logs from step 4 for a "Skipping arima for AAPL — existing run
found" message, which would mean the dedup check is *still* matching
(a different bug than the one fixed), versus no scheduler activity at
all (means step 4's wait wasn't long enough).

### 6. Quick sanity re-check (should take under a minute, not a full Round 1 repeat)

- `news-api` should still be in `manual` LLM mode from Round 1's fix —
  `curl -s http://localhost:8080/news/settings | python3 -m json.tool`
  should show `"llm_analysis_mode": "manual"`. If it's back to `auto`,
  that means the container was recreated from scratch (fresh DB) rather
  than restarted — worth noting, not necessarily a bug (a fresh DB
  reseeds from `.env`, which itself should already say `manual` per
  Round 1's `.env` fix — if `.env` still says `auto`, that's a leftover
  from before Round 1 and should be fixed there too).

## Where to record the outcome

Add a **`### Round 2`** section to `03-vinu-initial-analysis.md`'s
`## Bugs & Fixes Log` (do not edit or delete the existing `### Round 1`
section — round-by-round history is the point). Use the same
`**BUGS-2**` / `**FIXES-2**` heading format as Round 1. Include:
- Whether the fix verified as working (new `run_id`, growing obs count,
  current price scale) or not, with the actual numbers observed.
- If it didn't work: which failure mode from step 5 you saw, and enough
  detail (log excerpt, exact `has_existing_run` behavior observed) for
  a Round 3 fix attempt to start from real evidence instead of
  re-guessing.
- The step-6 sanity check result for `news-api`.

If Round 2 passes cleanly, that's the signal this small E2E check as a
whole is done — see `AGENTS.md`'s "what comes after this check" section
for what (not) to do next; don't start scaling up or building the
explanation docs as part of this same task unless asked.
