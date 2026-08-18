# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Slow/irregular CDN downloads (e.g. the 216MB nvidia-nccl_cu13 wheel pulled in
# by xgboost) exceeded pip's default 15s read-timeout during the first real
# build (observed ~117kB/s vs ~1MB/s on the host). Widen the tolerance so a
# transient slow stream doesn't kill the whole image build.
ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=10

# Triton (torch 2.13 CUDA kernels) JIT-compiles its driver shim with the C
# compiler at first CUDA use, so the image needs gcc at runtime; point its
# cache at the writable /tmp tmpfs (rootfs is read-only).
ENV TRITON_CACHE_DIR=/tmp/triton

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY vinu-infra /app/vinu-infra
RUN --mount=type=cache,target=/root/.cache/pip pip install -e "/app/vinu-infra[models]"

COPY vinu-tools /app/vinu-tools
RUN --mount=type=cache,target=/root/.cache/pip pip install -e "/app/vinu-tools[ml]"

COPY vinu-initial-analysis /app/vinu-initial-analysis

WORKDIR /app/vinu-initial-analysis

# --mount=type=cache persists pip's download cache across builds (keyed by
# this path, independent of layer-cache invalidation) -- without it, editing
# any single file upstream (e.g. vinu-infra/auth.py) forces a full re-download
# of this image's ~2GB CUDA/torch/chronos stack, confirmed 2026-08-18.
RUN --mount=type=cache,target=/root/.cache/pip pip install -e ".[dev]"

COPY vinu-initial-analysis/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

ENV VINU_INITIAL_ANALYSIS_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8083

ENTRYPOINT ["/app/entrypoint.sh"]
