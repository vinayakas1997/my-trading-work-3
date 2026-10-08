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

# Two processes in one container: the read-only HTTP API (the agent reads the hourly synthesis and the notable beliefs
# from it) and the worker loop that writes them. Without the API every reflection read in the agent failed with
# "connection refused", so the learning brain never reached a decision.
supervise vinu-reflection serve --host 0.0.0.0 --port "${VINU_REFLECTION_PORT:-8092}"
exec vinu-reflection worker
