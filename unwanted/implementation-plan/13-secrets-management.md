---
name: secrets-management
closes: "production-grade" gap raised in conversation (2026-08-17) — secrets live only in .env files, no vault/rotation
status: done — user chose self-hosted Docker Compose; Docker-secrets loader added, consumers wired, rotation documented, leaked Alpaca key file removed from git
priority: lower urgency than 10/11 — do once real broker credentials are actually in play, not purely academic before then
---

# Task: move real secrets out of plain `.env` files

## Goal

Establish a real secrets-management approach (a vault, a cloud secrets manager, or at minimum an
encrypted-at-rest store with access logging) for credentials that matter — broker API keys, LLM provider
keys, and the internal service-auth key that task 11 introduces — instead of plain-text `.env` files.

## Why

Found only `.env-example` / `.env.example` files across the tree — no vault, no secrets manager, no
rotation mechanism. Fine for solo local development; a real gap once this system holds live broker
credentials capable of moving real capital, or once task 11's internal-service auth key needs to be
shared across multiple deployed services without being checked into a file that inevitably ends up in a
backup, a screenshot, or a support ticket at some point.

## Current state (verified 2026-08-17)

- `.env-example` and per-package `.env.example` files exist across `vinu-initial-analysis`, `vinu-news`,
  `vinu-simulator`, `vinu-tools`, `vinu-strategy`, `vinu-research`, `vinu-stock-price`, and the repo root
  — consistent pattern, but all plain-text templates, nothing indicating an actual vault integration
  exists anywhere.
- Task 11 (service auth) will add a new shared-secret credential across services — this task should
  either land first (so task 11 stores its new key properly from day one) or task 11 should explicitly
  note it's using a placeholder `.env` approach until this task lands, to avoid silently becoming the
  fourth thing needing retrofitting.

## Steps

1. Decide the actual mechanism based on where this is deployed (cloud provider secrets manager if on
   AWS/GCP/Azure, HashiCorp Vault if self-hosted, or at minimum `git-crypt`/`sops`-encrypted files checked
   into the repo if neither of those is available yet) — this is an infrastructure/ops decision that
   depends on where the system actually runs; don't assume a specific vendor without confirming.
2. Migrate real credentials (broker API keys, LLM provider keys, the task-11 internal service-auth key)
   out of plain `.env` into the chosen mechanism.
3. Update each service's config loader to read from the new mechanism, falling back to `.env` only for
   genuinely non-sensitive local-dev defaults (feature flags, non-secret config), not real credentials.
4. Add access logging if the chosen mechanism supports it — knowing when a secret was read/rotated is
   part of the same traceability discipline this project already applies to trading decisions.
5. Document the rotation procedure, even if rotation isn't automated yet — a documented manual process
   beats no process.

## Acceptance criteria

- No real broker/LLM credentials exist in plain-text `.env` files in any deployed environment (local dev
  can remain an exception if clearly separated from staging/production config).
- The task-11 internal service-auth key is provisioned through this mechanism, not a bespoke `.env` entry.
- A documented rotation procedure exists.

## Dependencies

Loosely coupled with task 11 — ideally lands first or in tight coordination so the new service-auth key
isn't a second thing needing migration later.
