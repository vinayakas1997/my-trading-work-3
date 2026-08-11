FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e /app/vinu-infra

# vinu-research is now imported in-process by vinu_portfolio/service.py
# (_list_llm_strategies/_fetch_outcome_confidence/_fetch_trade_plan --
# component-consolidation-plan.md's vinu-research migration, extended to
# this codebase). Same transitive deps vinu-research's own Dockerfile
# installs, in the same order.
COPY vinu-stock-price /app/vinu-stock-price
RUN pip install --no-cache-dir -e /app/vinu-stock-price
COPY vinu-tools /app/vinu-tools
RUN pip install --no-cache-dir -e /app/vinu-tools
COPY vinu-simulator /app/vinu-simulator
RUN pip install --no-cache-dir -e /app/vinu-simulator
COPY vinu-research /app/vinu-research
RUN pip install --no-cache-dir -e /app/vinu-research

COPY vinu-portfolio /app/vinu-portfolio

WORKDIR /app/vinu-portfolio

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-portfolio/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

ENV VINU_PORTFOLIO_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8090

ENTRYPOINT ["/app/entrypoint.sh"]
