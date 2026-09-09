"""Event-risk calendar (how-to-make-it-live.md #2, Stage 4).

A small earnings + macro-economic calendar kept in local SQLite, refreshed once
a day from Finnhub by the ingest worker, and read by vinu-live's entry path to
blackout new positions ahead of a scheduled event. Lives inside
vinu-stock-price because it is decision-time market data about a symbol -- the
same role as the /stock/quote spread read -- not a service of its own.
"""
