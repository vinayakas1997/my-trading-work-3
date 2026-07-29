FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-tools /app/vinu-tools
RUN pip install --no-cache-dir -e /app/vinu-tools

COPY vinu-live /app/vinu-live

WORKDIR /app/vinu-live

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-live/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_LIVE_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8091

ENTRYPOINT ["/app/entrypoint.sh"]
