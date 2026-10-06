#!/usr/bin/env bash
# Reset the system's DERIVED state so it runs from a clean slate, without losing anything expensive to rebuild.
#
#   KEPT     stock-price (candles, events, catalog), news (articles), models (weights), shared (watchlist),
#            screener rules and tickers: raw inputs and settings, slow or impossible to re-fetch.
#   CLEARED  everything the system computed or decided: analysis, summaries, sessions, research runs, strategies,
#            simulations, trade plans, execution log, allocation history, reflection, the LLM queue history.
#
# Nothing is deleted: cleared files are MOVED to data/_backup_<timestamp>/ with the same layout, so a reset can be
# undone by moving them back. Alpaca (the paper account) is outside our data and is untouched.
#
# Usage (from vinu-components/):  scripts/fresh_start.sh          # stops the stack, moves files, starts it again
set -euo pipefail
cd "$(dirname "$0")/.."

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="data/_backup_$STAMP"
KEEP_RUNNING="stock-api news-api"

# whole folders that are derived state
CLEAR_DIRS="agent features initial-analysis live llm-gateway portfolio reflection research simulator strategy strategy-evaluation"
# derived files inside folders that are otherwise kept
CLEAR_FILES="screener/screener_audit.db screener/screener_ranker_churn.db screener/screener_ranker_snapshots.db screener/screener_rankers.db"

echo "stopping everything except: $KEEP_RUNNING"
SERVICES="$(docker compose config --services | grep -v -x -e hindsight-llm -e models-api || true)"
STOP=""
for s in $SERVICES; do
  keep=0; for k in $KEEP_RUNNING; do [ "$s" = "$k" ] && keep=1; done
  [ "$keep" = "0" ] && STOP="$STOP $s"
done
docker compose stop $STOP >/dev/null

mkdir -p "$BACKUP"
for d in $CLEAR_DIRS; do
  [ -d "data/$d" ] || continue
  mkdir -p "$BACKUP/$(dirname "$d")"
  mv "data/$d" "$BACKUP/$d"
  mkdir -p "data/$d"
  echo "cleared data/$d"
done
for f in $CLEAR_FILES; do
  # the sqlite sidecar files (-wal, -shm) must move with their database
  for g in "data/$f" "data/$f-wal" "data/$f-shm"; do
    [ -e "$g" ] || continue
    mkdir -p "$BACKUP/$(dirname "${g#data/}")"
    mv "$g" "$BACKUP/${g#data/}"
  done
  echo "cleared data/$f"
done

echo "starting the stack"
bash scripts/stack.sh up >/dev/null 2>&1 || docker compose up -d >/dev/null
echo "backup of the cleared state: $BACKUP"
