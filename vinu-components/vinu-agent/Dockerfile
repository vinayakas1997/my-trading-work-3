FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra/ /app/vinu-infra/
RUN pip install -e /app/vinu-infra

# vinu-research is imported in-process (New-talk-agents/implementation/
# 13-vinu-research-in-process-migration.md) -- order_guard.py's active-
# artifact safety check and every other migrated call site import
# vinu_research directly, with no separate service call. Without these
# installed in this image, those imports raise ImportError at call time;
# most call sites catch that broadly and fail open (e.g. order_guard.py's
# own documented "missing/corrupt local DB shouldn't silently block all
# trading" policy), which means the real bug (package not installed) was
# indistinguishable from a legitimate fail-open case and shipped silently.
# vinu-research itself depends on these three in-process (see its own
# Dockerfile), so they're installed here in the same order.
COPY vinu-stock-price/ /app/vinu-stock-price/
RUN pip install -e /app/vinu-stock-price
COPY vinu-tools/ /app/vinu-tools/
RUN pip install -e /app/vinu-tools
COPY vinu-simulator/ /app/vinu-simulator/
RUN pip install -e /app/vinu-simulator
COPY vinu-research/ /app/vinu-research/
RUN pip install -e /app/vinu-research

COPY vinu-agent/ /app/vinu-agent/
RUN pip install -e /app/vinu-agent

COPY vinu-agent/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
RUN pip install --no-cache-dir py-spy
USER app

EXPOSE 8086

ENTRYPOINT ["/app/entrypoint.sh"]
