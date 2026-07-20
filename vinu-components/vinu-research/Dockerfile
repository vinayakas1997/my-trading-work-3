FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-research /app/vinu-research

WORKDIR /app/vinu-research

RUN pip install --no-cache-dir -e ".[dev]"

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_RESEARCH_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8087
