FROM python:3.12-slim

# Slow/irregular CDN downloads (e.g. the 216MB nvidia-nccl_cu13 wheel pulled in
# by xgboost) exceeded pip's default 15s read-timeout during the first real
# build (observed ~117kB/s vs ~1MB/s on the host). Widen the tolerance so a
# transient slow stream doesn't kill the whole image build.
ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=10

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e "/app/vinu-infra[models]"

COPY vinu-tools /app/vinu-tools
RUN pip install --no-cache-dir -e "/app/vinu-tools[ml]"

COPY vinu-initial-analysis /app/vinu-initial-analysis

WORKDIR /app/vinu-initial-analysis

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-initial-analysis/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

ENV VINU_INITIAL_ANALYSIS_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8083

ENTRYPOINT ["/app/entrypoint.sh"]
