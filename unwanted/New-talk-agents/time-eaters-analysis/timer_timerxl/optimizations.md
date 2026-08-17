# timer_timerxl — Optimizations

## ✅ APPLIED: HF_HOME fix (unblocked the real model)
`docker-compose.yml` now sets `HF_HOME: /home/app/.cache/huggingface` for
`initial-analysis-api`, redirecting the transformers remote-code cache to the
writable tmpfs mount instead of the leaked Windows `HOME` path.

**Verification:** real Timer loads (`model_backend == "pretrained"`), ~0.05s/call.
`test_timer_timerxl.py:95-103` should now pass with `pretrained`.

## Not needed
- bf16/quantization: 0.05s/call is already negligible.
- num_samples reduction: single forward pass, no sampling loop.
- Cross-process model reuse would only save the ~27s one-time load per process — only
  worth it if the suite's per-process loads become the bottleneck.

## Watch out
The leaked `HOME` from `.env` affects ANY container that uses `trust_remote_code=True`
models. If more angles adopt remote-code checkpoints, they all need `HF_HOME` (or a
fixed `HOME`) in compose. Consider fixing `.env`'s HOME leak at the source as follow-up.
