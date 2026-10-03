FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e "/app/vinu-infra[models]"

COPY vinu-news /app/vinu-news

WORKDIR /app/vinu-news

# No torch here: FinBERT scoring is done by the model-serving service (models-api, VINU_MODEL_SERVICE_URL).
RUN pip install --no-cache-dir -e .

# FinBERT is NOT baked into the image anymore — weights live in the shared
# models dir (data/models/finbert, see vinu-infra/models.py), downloaded via
# `make models` and mounted read-only into the container at /models.

COPY vinu-news/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

ENV VINU_NEWS_DB_PATH=/data/news.db
ENV PYTHONUNBUFFERED=1

VOLUME ["/data"]

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
