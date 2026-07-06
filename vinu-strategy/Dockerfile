FROM python:3.12-slim

WORKDIR /app

COPY . /app/vinu-strategy

WORKDIR /app/vinu-strategy

RUN pip install --no-cache-dir -e ".[dev]"

ENV VINU_STRATEGY_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8084
