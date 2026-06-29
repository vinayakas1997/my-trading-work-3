FROM python:3.12-slim

WORKDIR /app

COPY . /app/vinu-news

WORKDIR /app/vinu-news

RUN pip install --no-cache-dir -e .

ENV VINU_NEWS_DB_PATH=/data/news.db

VOLUME ["/data"]

EXPOSE 8080
