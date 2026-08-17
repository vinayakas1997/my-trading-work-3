# timer_timerxl — Bottlenecks

## ✅ RESOLVED: Real model failed to load (blocker fixed)
The real Timer model failed to load with `OSError(30, 'Read-only file system')`.

**Root cause:** `.env` leaks the Windows host `HOME=C:Usersvinay` into the container.
`AutoModelForCausalLM.from_pretrained(..., trust_remote_code=True)` writes the fetched
remote code to `$HOME/.cache/huggingface/modules/` → resolves to a nonexistent Windows
path on a read-only rootfs → OSError 30 → silent fallback to the statistical proxy.

**Fix applied:** `docker-compose.yml` sets `HF_HOME: /home/app/.cache/huggingface`
(the compose tmpfs mount for `/home/app/.cache`). Verified: `backend: pretrained` after fix.

## Remaining notes
- Load is ~27s per process (in-process `_MODEL_CACHE` only, `timer_timerxl/compute.py:71`).
- Per-call cost ~0.05s — negligible. No further optimization needed.
