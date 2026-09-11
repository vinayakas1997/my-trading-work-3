FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e /app/vinu-infra

COPY vinu-screener /app/vinu-screener

WORKDIR /app/vinu-screener

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-screener/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

ENV VINU_SCREENER_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8095

ENTRYPOINT ["/app/entrypoint.sh"]
