FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-stock-price /app/vinu-stock-price
RUN pip install --no-cache-dir -e /app/vinu-stock-price

COPY vinu-tools /app/vinu-tools
RUN pip install --no-cache-dir -e /app/vinu-tools

COPY vinu-simulator /app/vinu-simulator
RUN pip install --no-cache-dir -e /app/vinu-simulator

COPY vinu-research /app/vinu-research

WORKDIR /app/vinu-research

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-research/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_RESEARCH_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8087

ENTRYPOINT ["/app/entrypoint.sh"]
