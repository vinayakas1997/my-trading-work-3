FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-strategy /app/vinu-strategy

WORKDIR /app/vinu-strategy

RUN pip install --no-cache-dir -e ".[dev]"

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_STRATEGY_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8084
