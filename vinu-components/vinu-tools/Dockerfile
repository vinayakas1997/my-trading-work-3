FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e /app/vinu-infra

COPY vinu-tools /app/vinu-tools

WORKDIR /app/vinu-tools

RUN pip install --no-cache-dir -e .

COPY vinu-tools/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

ENV VINU_FEATURES_DATA_DIR=/data
ENV VINU_FEATURES_META_DB_PATH=/data/meta.db

VOLUME ["/data"]

EXPOSE 8082

ENTRYPOINT ["/app/entrypoint.sh"]
