# Plan - 22 Infra Secrets Docker

Goal: 9 healthy, secrets safe, retry same, slim later.

Files touched:
- `vinu-components/docker-compose.yml` services ports mounts caps health depends + agent tmpfs /nonexistent:rw,mode=1777,exec fixed 06:51.
- `vinu-components/vinu-infra/secrets_loader.py:44` fallback warning.
- `scripts/setup-secrets.sh --check` ready.
- Retry: allocator pattern `inefficiencies-A-J.md:F` to simulator + research HTTP.
- Dockerfile slim CPU torch + warm /models host.

Steps:
1. Secrets check + .env hygiene (URLs only, keys in files).
2. Retry 10s x3 simulator + research same as allocator.
3. Image slim warm cache last infra window.

Knobs: DATA_ROOT, HOST/PORT, MODELS_DIR, HTTP_RETRY 10s x3 (see 10).
Acceptance: --check ready, no plain leak in inspect, flap fixed, 6.52 to 3.5GB later.
