FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-initial-analysis /app/vinu-initial-analysis

WORKDIR /app/vinu-initial-analysis

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-initial-analysis/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_INITIAL_ANALYSIS_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8083

ENTRYPOINT ["/app/entrypoint.sh"]
