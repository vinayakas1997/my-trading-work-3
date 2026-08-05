FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e /app/vinu-infra

COPY vinu-stock-price /app/vinu-stock-price

WORKDIR /app/vinu-stock-price

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-stock-price/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

ENV VINU_STOCK_DATA_ROOT=/data
ENV VINU_STOCK_META_DB_PATH=/data/meta.db

VOLUME ["/data"]

EXPOSE 8081

ENTRYPOINT ["/app/entrypoint.sh"]
