# Group 1 fold (component-consolidation-plan.md): one deploy artifact for
# vinu-strategy + vinu-simulator instead of two separate containers -- both
# are confirmed genuinely stateless (no background worker, pure
# request/response APIs), the lowest-risk fold in that plan.
#
# No new Python package here on purpose -- vinu_strategy/server/merged_app.py
# (in the real vinu-strategy package) does the actual route-combining; this
# directory only exists to build one image containing both real codebases,
# same relationship vinu-research's own Dockerfile already has to its own
# transitive deps (vinu-stock-price/vinu-tools/vinu-simulator).
FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e /app/vinu-infra

COPY vinu-simulator /app/vinu-simulator
RUN pip install --no-cache-dir -e /app/vinu-simulator

COPY vinu-strategy /app/vinu-strategy
RUN pip install --no-cache-dir -e "/app/vinu-strategy[dev]"

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

# Each side keeps its own real data-root env var/subdirectory -- unchanged
# storage layout, just two volumes into one container instead of two.
ENV VINU_STRATEGY_DATA_ROOT=/data/strategy
ENV VINU_SIMULATOR_DATA_ROOT=/data/simulator

VOLUME ["/data/strategy", "/data/simulator"]

EXPOSE 8084

CMD ["vinu-strategy", "serve-merged", "--host", "0.0.0.0", "--port", "8084"]
