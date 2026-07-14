FROM python:3.12-slim

WORKDIR /app

COPY vinu-lib /app/vinu-lib
RUN pip install --no-cache-dir -e /app/vinu-lib

COPY vinu-news /app/vinu-news

WORKDIR /app/vinu-news

RUN pip install --no-cache-dir -e .

ENV VINU_NEWS_DB_PATH=/data/news.db

VOLUME ["/data"]

EXPOSE 8080
