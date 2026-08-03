FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-news /app/vinu-news

WORKDIR /app/vinu-news

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch>=2.2 \
    && pip install --no-cache-dir -e .

# Bake FinBERT into the image at build time — the container's filesystem is
# read-only at runtime except /data and tmpfs (wiped on restart), so the
# model can't be downloaded lazily on first use without network access and
# a re-download on every restart. The --mount=type=cache keeps the HF hub
# download across builds, so only the first build pays the ~430MB fetch.
RUN --mount=type=cache,target=/root/.cache/huggingface \
    python3 -c "\
from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
tok = AutoTokenizer.from_pretrained('ProsusAI/finbert'); \
model = AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert'); \
tok.save_pretrained('/app/models/finbert'); \
model.save_pretrained('/app/models/finbert')" \
    && chmod -R a+rX /app/models

COPY vinu-news/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_NEWS_DB_PATH=/data/news.db

VOLUME ["/data"]

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
