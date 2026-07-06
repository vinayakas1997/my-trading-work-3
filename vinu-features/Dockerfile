FROM python:3.12-slim

WORKDIR /app

COPY . /app/vinu-features

WORKDIR /app/vinu-features

RUN pip install --no-cache-dir -e .

ENV VINU_FEATURES_DATA_DIR=/data
ENV VINU_FEATURES_META_DB_PATH=/data/meta.db

VOLUME ["/data"]

EXPOSE 8082