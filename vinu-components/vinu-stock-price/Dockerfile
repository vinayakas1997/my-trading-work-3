FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-stock-price /app/vinu-stock-price

WORKDIR /app/vinu-stock-price

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-stock-price/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_STOCK_DATA_ROOT=/data
ENV VINU_STOCK_META_DB_PATH=/data/meta.db

VOLUME ["/data"]

EXPOSE 8081

ENTRYPOINT ["/app/entrypoint.sh"]
