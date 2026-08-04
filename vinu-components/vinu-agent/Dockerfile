FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib/ /app/vinu-lib/
RUN pip install -e /app/vinu-lib

COPY vinu-agent/ /app/vinu-agent/
RUN pip install -e /app/vinu-agent

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

EXPOSE 8086

CMD ["vinu-agent", "serve", "--host", "0.0.0.0", "--port", "8086"]
