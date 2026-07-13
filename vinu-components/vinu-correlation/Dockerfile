FROM python:3.12-slim

WORKDIR /app

COPY . /app/vinu-correlation

WORKDIR /app/vinu-correlation

RUN pip install --no-cache-dir -e ".[dev]"

ENV VINU_CORRELATION_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8083
