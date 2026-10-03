# syntax=docker/dockerfile:1
# Model-serving service: the ONLY image that installs torch. It runs the model-category analysis angles (code imported
# from vinu-initial-analysis, installed with its `models` extra) and FinBERT scoring for vinu-news.
FROM python:3.12-slim

ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=10

# Triton (torch CUDA kernels) JIT-compiles a driver shim at first CUDA use: gcc at runtime, writable exec cache.
ENV TRITON_CACHE_DIR=/triton-cache

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY vinu-infra /app/vinu-infra
RUN --mount=type=cache,target=/root/.cache/pip pip install -e "/app/vinu-infra[models]"

COPY vinu-tools /app/vinu-tools
RUN --mount=type=cache,target=/root/.cache/pip pip install -e "/app/vinu-tools[ml]"

# The angle code lives in vinu-initial-analysis; the `models` extra brings torch, chronos-forecasting, timesfm.
COPY vinu-initial-analysis /app/vinu-initial-analysis
RUN --mount=type=cache,target=/root/.cache/pip pip install -e "/app/vinu-initial-analysis[models]"

# FinBERT (used through /models/finbert/score)
RUN --mount=type=cache,target=/root/.cache/pip pip install "transformers>=4.40"

COPY vinu-models /app/vinu-models
WORKDIR /app/vinu-models
RUN --mount=type=cache,target=/root/.cache/pip pip install -e .

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

ENV VINU_MODELS_PORT=8096

EXPOSE 8096

ENTRYPOINT ["vinu-model-server", "--host", "0.0.0.0", "--port", "8096"]
