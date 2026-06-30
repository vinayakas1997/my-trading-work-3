FROM python:3.12-slim

WORKDIR /app

COPY . /app/vinu-stock-price

WORKDIR /app/vinu-stock-price

RUN pip install --no-cache-dir -e ".[dev]"

ENV VINU_STOCK_DATA_ROOT=/data
ENV VINU_STOCK_META_DB_PATH=/data/meta.db

VOLUME ["/data"]

EXPOSE 8081
