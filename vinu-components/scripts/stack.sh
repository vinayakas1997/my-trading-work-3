#!/usr/bin/env bash
# The one way to build and run the stack, so the same mistakes cannot come back:
#   * models-api is dormant (compose profile "models"), so it is never built or started here
#   * secrets live only in secrets/ files; .env must not hold their values (checked by `check`)
#   * the data folders are made writable for the container user before start (Docker Desktop on Windows creates
#     them root-owned and the services then fail with "unable to open database file")
#
# A fix only takes effect once its image is rebuilt AND the container recreated, so:
#   * `stale` lists every running service older than its source (exit 1 if any)
#   * `deploy` rebuilds and recreates exactly those services, then re-checks
#
# Usage (from vinu-components/):  scripts/stack.sh prepare | check | build | up | down | ps | stale | deploy
set -euo pipefail
cd "$(dirname "$0")/.."

DATA_DIRS="stock-price screener features initial-analysis live agent research portfolio strategy simulator shared strategy-evaluation news reflection llm-gateway"

prepare() {
  [ -f .env ] || { cp .env-example .env; echo "created .env from .env-example"; }
  for d in $DATA_DIRS; do mkdir -p "data/$d"; done
  for s in vinu_api_key alpaca_api_key alpaca_api_secret vinu_llm_api_key polygon_api_key fmp_api_key tushare_token telegram_token discord_token; do
    [ -f "secrets/$s" ] || { mkdir -p secrets; : > "secrets/$s"; echo "created empty secrets/$s (fill it in)"; }
  done
  local here; here="$(pwd -W 2>/dev/null || pwd)"
  MSYS_NO_PATHCONV=1 docker run --rm -v "$here/data:/d" python:3.12-slim \
    sh -c "for x in $DATA_DIRS; do chmod -R a+rwX /d/\$x; done"
  echo "data folders are writable"
}

check() {
  python - <<'PY'
import re, sys, pathlib
secret_names = {"VINU_API_KEY", "ALPACA_API_KEY", "ALPACA_API_SECRET", "VINU_LLM_API_KEY", "POLYGON_API_KEY", "FMP_API_KEY"}
bad = []
for f in (".env", ".env-example"):
    p = pathlib.Path(f)
    if not p.exists():
        continue
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z_]+)=(.+)$", line)
        if m and m.group(1) in secret_names and m.group(2).strip():
            bad.append(f"{f}: {m.group(1)} has a value; put it in secrets/ and leave this blank")
if bad:
    print("\n".join(bad)); sys.exit(1)
print("secrets are only in secrets/ files")
PY
  grep -q '^ALPACA_PAPER=true' .env || { echo "ALPACA_PAPER=true is not pinned in .env"; exit 1; }
  echo "broker is pinned to paper"
}

services() { docker compose config --services; }   # the default profile only: models-api is excluded

build() { prepare; check; docker compose build $(services); }
up()    { prepare; check; docker compose up -d $(services); }
down()  { docker compose down; }
ps()    { docker compose ps --format "table {{.Name}}\t{{.Status}}"; }
stale() { python scripts/stale_images.py; }
deploy() {
  prepare; check
  local names
  # stale_images.py exits 1 when anything is stale; under `set -o pipefail` that would abort the script here
  names=$(python scripts/stale_images.py | awk '/^  STALE/ {print $2}' || true)
  [ -z "$names" ] && { echo "nothing is stale"; return 0; }
  # A research run takes 5 to 100 minutes and a restart of any service it uses kills it (problem log O7, O17: 24 of 30 failed
  # runs in a day were restarts). Refuse to restart those services while a run is in flight, unless told to.
  if [ "${FORCE:-}" != "1" ] && echo " $names " | grep -qE " (agent-api|research-api|llm-gateway|quant-core-api) "; then
    running=$(python scripts/stack_db.py agent-api team_runs.db "select count(*) from team_runs where status='running'" 2>/dev/null | grep -oE '\([0-9]+' | tr -d '(' || echo 0)
    if [ "${running:-0}" -gt 0 ]; then
      echo "refusing to deploy: $running research/team run(s) in flight would be killed by restarting: $names"
      echo "wait for them to finish (python scripts/pipeline_health.py lists them) or run: FORCE=1 scripts/stack.sh deploy"
      return 1
    fi
  fi
  docker compose build $names
  docker compose up -d $names
  python scripts/stale_images.py
}

case "${1:-}" in
  prepare|check|build|up|down|ps|stale|deploy) "$1" ;;
  *) echo "usage: scripts/stack.sh prepare|check|build|up|down|ps|stale|deploy"; exit 2 ;;
esac
