FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-portfolio /app/vinu-portfolio

WORKDIR /app/vinu-portfolio

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-portfolio/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_PORTFOLIO_DATA_ROOT=/data

VOLUME ["/data"]

EXPOSE 8090

ENTRYPOINT ["/app/entrypoint.sh"]
