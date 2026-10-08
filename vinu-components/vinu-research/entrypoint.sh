#!/bin/bash
set -e

# A background worker that crashes (non-zero exit) is started again after a growing pause (10 s, 20 s ... 5 min; the count
# resets after 10 healthy minutes). A clean exit (0) ends it. Without this a worker that died at start-up stayed dead while
# the container kept reporting healthy: after the news layer-2 deploy the ingest loop was dead for minutes and nothing said so.
supervise() {
  (
    n=0
    while true; do
      started=$SECONDS
      "$@" && rc=0 || rc=$?
      if [ "$rc" -eq 0 ]; then echo "[supervisor] '$*' finished (exit 0)" >&2; break; fi
      if [ $((SECONDS - started)) -gt 600 ]; then n=0; fi
      n=$((n + 1)); pause=$((n * ${VINU_SUPERVISE_STEP:-10})); [ "$pause" -gt 300 ] && pause=300
      echo "[supervisor] '$*' exited with $rc; restarting in ${pause}s" >&2
      sleep "$pause"
    done
  ) &
}

supervise vinu-research schedule-decay --interval-hours 24
supervise vinu-research schedule-freshness
exec vinu-research serve --host 0.0.0.0 --port 8087
