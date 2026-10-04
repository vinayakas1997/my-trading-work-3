#!/bin/bash
# The strategy service reads its YAML strategies from $VINU_STRATEGY_STRATEGIES_DIR (a mounted data volume, empty on a
# fresh machine), while the shipped strategies live inside the image. Seed the volume once: copy only files that are not
# there yet, so a strategy you edit or add in the volume is never overwritten.
set -e
dir="${VINU_STRATEGY_STRATEGIES_DIR:-/data/strategy/strategies}"
mkdir -p "$dir"
cp -n /app/vinu-strategy/strategies/*.yaml "$dir"/ 2>/dev/null || true
echo "strategies available: $(ls "$dir" | wc -l) in $dir"
exec "$@"
