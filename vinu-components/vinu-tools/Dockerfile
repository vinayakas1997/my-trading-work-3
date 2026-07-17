FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-tools /app/vinu-tools

WORKDIR /app/vinu-tools

RUN pip install --no-cache-dir -e .

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_FEATURES_DATA_DIR=/data
ENV VINU_FEATURES_META_DB_PATH=/data/meta.db

VOLUME ["/data"]

EXPOSE 8082