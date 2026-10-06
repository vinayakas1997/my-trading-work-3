#!/usr/bin/env bash
# Run every package's tests INSIDE the built service images (the real environment: the same Python, the same
# installed packages), not on the host. Host runs gave false failures both ways (missing statsmodels/openai on the
# host) and hid real ones.
#
#   * each run is a throwaway container with no data volumes, so tests can never touch live data
#   * it runs as root because tests write a relative data/ folder and the image user cannot write under /app
#   * vinu-infra's repo-level tests (stack guards, compose wiring, edge manifest) read files no image carries; run
#     them on the host: python -m pytest vinu-infra/tests
#   * it refuses to run against stale images: run `scripts/stack.sh deploy` first
#
# Usage (from vinu-components/):  scripts/test_in_containers.sh [service ...]     (default: every service)
set -uo pipefail
cd "$(dirname "$0")/.."

SERVICES="${*:-stock-api screener-api features-api news-api portfolio-api quant-core-api research-api live-api agent-api reflection-worker initial-analysis-api}"
OUT="${TEST_OUT:-logs/container-tests}"
mkdir -p "$OUT"

python scripts/stale_images.py >/dev/null || { echo "stale images: run scripts/stack.sh deploy first"; python scripts/stale_images.py | grep STALE; exit 2; }

status=0
# Services refuse to start without an explicit data root, so give every one a throwaway folder.
ENVS=""
for v in $(grep -oE "^VINU_[A-Z_]*DATA_ROOT" .env-example | sort -u); do ENVS="$ENVS -e $v=/tmp/testdata/$v"; done
HOST="$(pwd -W 2>/dev/null || pwd)"
for svc in $SERVICES; do
  # Run the host's current tests against the IMAGE's code: only the code has to be the real build, and a tests-only
  # edit then needs no rebuild.
  MOUNTS=""
  for p in $(MSYS_NO_PATHCONV=1 docker run --rm --entrypoint ls "vinu-components-$svc" /app | grep "^vinu-"); do
    [ -d "vinu-${p#vinu-}/tests" ] && MOUNTS="$MOUNTS -v $HOST/$p/tests:/app/$p/tests:ro"
  done
  SKIP_PKG=""; [ "$svc" = "quant-core-api" ] && SKIP_PKG="vinu-portfolio"
  MSYS_NO_PATHCONV=1 docker run --rm --user root --cpus 2 -e SKIP_PKG="$SKIP_PKG" $ENVS $MOUNTS --entrypoint sh "vinu-components-$svc" -c '
    # the images carry pytest but not its async plugin, so every async test would fail with
    # "async def functions are not natively supported" (a missing tool, not a code bug)
    pip install -q pytest-asyncio >/dev/null 2>&1
    for d in /app/vinu-*/; do
      [ -d "$d/tests" ] || continue
      # quant-core carries portfolio code only so the strategy service can import it, without the research package
      # those tests need; the portfolio's own tests run in the portfolio-api image (and agent, research, reflection).
      [ "$SKIP_PKG" = "$(basename $d)" ] && { echo "### $(basename $d): skipped in this image (its tests need packages this image does not carry)"; continue; }
      cd "$d"
      args="tests -q --no-header -p no:cacheprovider --tb=line -rfE"
      # these read repo-level files (docker-compose.yml, the edge manifest, the source tree) that no image carries
      [ "$(basename $d)" = "vinu-infra" ] && args="$args --ignore=tests/test_stack_guards.py --ignore=tests/test_compose_wiring.py --ignore=tests/test_edge_contracts.py --ignore=tests/test_pipeline_edges.py"
      res=$(python -m pytest $args 2>&1)
      echo "### $(basename $d): $(echo "$res" | grep -E "passed|failed|error" | tail -1)"
      echo "$res" | grep -E "^FAILED|^ERROR" | cut -c1-200 | head -60
    done' > "$OUT/$svc.txt" 2>&1
done

echo "package results by image (the shared packages are identical in every image that carries them):"
total=0
for svc in $SERVICES; do
  echo "== $svc"
  grep "^###" "$OUT/$svc.txt"
  total=$((total + $(grep -cE "^FAILED|^ERROR" "$OUT/$svc.txt")))
done
echo "failing tests recorded: $total  (details in $OUT/<service>.txt)"
[ "$total" = "0" ] || status=1
exit $status
