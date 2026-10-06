FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e /app/vinu-infra

COPY vinu-llm-gateway /app/vinu-llm-gateway

WORKDIR /app/vinu-llm-gateway

RUN pip install --no-cache-dir -e ".[dev]"

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_LLM_GATEWAY_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8099

ENTRYPOINT ["vinu-llm-gateway", "serve", "--host", "0.0.0.0", "--port", "8099"]
