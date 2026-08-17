#!/usr/bin/env bash
# Populate the ./secrets/ files that docker-compose mounts into the services
# (implementation-plan task 13). Run BEFORE `docker compose up`.
#
# For each credential it looks, in order, at: an already-existing secret file
# (kept), the current shell env, then the values in ./.env.
#
# REQUIRED secrets (the stack cannot function without them) cause this script
# to exit non-zero if still empty after populating -- same "no silent
# default" discipline vinu_infra.config.require_data_root already applies to
# data roots. OPTIONAL secrets (integrations you may not have set up yet,
# e.g. Telegram/Discord) are allowed to stay empty; the loaders fall back to
# the legacy env var at runtime either way.
#
# Files are written mode 0600 and the whole directory is gitignored, so real
# credentials never reach git.
#
# Usage:
#   scripts/setup-secrets.sh          populate + fail if a REQUIRED secret is empty
#   scripts/setup-secrets.sh --check  validate only, write nothing, same exit code

set -euo pipefail
cd "$(dirname "$0")/.."

CHECK_ONLY=0
if [ "${1:-}" = "--check" ]; then
  CHECK_ONLY=1
fi

SECRETS_DIR="${VINU_SECRETS_DIR:-$(pwd)/secrets}"
ENV_FILE="$(pwd)/.env"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# name:file <-> env var mapping (secret file name matches what the code reads
# from /run/secrets/<name>; the env var is the legacy fallback).
declare -A SECRETS=(
  [vinu_api_key]="VINU_API_KEY"
  [alpaca_api_key]="ALPACA_API_KEY"
  [alpaca_api_secret]="ALPACA_API_SECRET"
  [polygon_api_key]="POLYGON_API_KEY"
  [fmp_api_key]="FMP_API_KEY"
  [tushare_token]="TUSHARE_TOKEN"
  [vinu_llm_api_key]="VINU_LLM_API_KEY"
  [telegram_token]="TELEGRAM_TOKEN"
  [discord_token]="DISCORD_TOKEN"
)

# The stack cannot function correctly without these:
#   vinu_api_key      -- empty means auth.require_auth no-ops and every
#                         internal route is open with zero enforcement
#   alpaca_api_key/secret -- the only broker integration wired up
#   vinu_llm_api_key  -- every agent team needs a primary LLM provider
# Everything else (market-data extras, Telegram/Discord delivery) is a real
# but optional integration -- fine to leave empty until you set it up.
REQUIRED_NAMES=(vinu_api_key alpaca_api_key alpaca_api_secret vinu_llm_api_key)

is_required() {
  local name="$1"
  for r in "${REQUIRED_NAMES[@]}"; do
    [ "$r" = "$name" ] && return 0
  done
  return 1
}

env_value() {
  local var="$1"
  if [ -n "${!var:-}" ]; then
    printf '%s' "${!var}"
    return
  fi
  if [ -f "$ENV_FILE" ]; then
    local line
    line="$(grep -E "^${var}=" "$ENV_FILE" | tail -1 || true)"
    printf '%s' "${line#*=}"
  fi
}

missing_required=()

for name in "${!SECRETS[@]}"; do
  file="$SECRETS_DIR/$name"

  if [ "$CHECK_ONLY" = "1" ]; then
    if [ -f "$file" ] && [ -s "$file" ]; then
      value="present"
    else
      value="$(env_value "${SECRETS[$name]}")"
    fi
    if [ -z "$value" ]; then
      if is_required "$name"; then
        echo "MISSING   $name (required) -- set ${SECRETS[$name]} or ./secrets/$name"
        missing_required+=("$name")
      else
        echo "empty     $name (optional) -- falls back to ${SECRETS[$name]} env var"
      fi
    else
      echo "ok        $name"
    fi
    continue
  fi

  if [ -f "$file" ] && [ -s "$file" ]; then
    echo "keeping   $name (already populated)"
    continue
  fi
  value="$(env_value "${SECRETS[$name]}")"
  umask 177
  printf '%s\n' "$value" > "$file"
  chmod 600 "$file"
  if [ -n "$value" ]; then
    echo "populated $name from ${SECRETS[$name]}"
  elif is_required "$name"; then
    echo "MISSING   $name (required) -- set ${SECRETS[$name]} or ./secrets/$name"
    missing_required+=("$name")
  else
    echo "empty     $name (optional) -- falls back to ${SECRETS[$name]} env var"
  fi
done

echo
if [ ${#missing_required[@]} -gt 0 ]; then
  echo "FAILED: ${#missing_required[@]} required secret(s) missing: ${missing_required[*]}"
  echo "set them in .env (or export in the shell) and re-run this script before 'docker compose up'."
  exit 1
fi

if [ "$CHECK_ONLY" = "1" ]; then
  echo "all required secrets present"
else
  echo "secret files ready under $SECRETS_DIR"
  echo "rotate any real value by editing the file and running: docker compose up -d --force-recreate"
fi
