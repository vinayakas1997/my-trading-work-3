FROM python:3.12-slim

WORKDIR /app

COPY vinu-infra /app/vinu-infra
RUN pip install --no-cache-dir -e /app/vinu-infra

# vinu-agent is a real dependency (not a lightweight one -- discord.py/
# python-telegram-bot/openai/yfinance come along with it, plus
# vinu-agent's own in-process link to vinu-research and *its* three
# transitive deps below), accepted deliberately: vinu-reflection reads
# vinu-agent's storage classes in-process (mount-and-import), the same
# trade this codebase already makes for vinu-agent -> vinu-research via
# research_link.py. Same install order as vinu-agent/Dockerfile. See
# vinu_reflection/reflection/decision_process.py's module docstring.
COPY vinu-stock-price /app/vinu-stock-price
RUN pip install --no-cache-dir -e /app/vinu-stock-price
COPY vinu-tools /app/vinu-tools
RUN pip install --no-cache-dir -e /app/vinu-tools
COPY vinu-simulator /app/vinu-simulator
RUN pip install --no-cache-dir -e /app/vinu-simulator
COPY vinu-research /app/vinu-research
RUN pip install --no-cache-dir -e /app/vinu-research
COPY vinu-agent /app/vinu-agent
RUN pip install --no-cache-dir -e /app/vinu-agent

# vinu-live -- for E's pair-correlation piece (BookBackend/
# CorrelationMonitorStore, read in-process against a mounted copy of
# vinu-live's data root). vinu-tools (above) is its own prerequisite,
# already installed.
COPY vinu-live /app/vinu-live
RUN pip install --no-cache-dir -e /app/vinu-live

# vinu-screener -- for I/X's screener cross-checks (RankerStore/
# RankerChurnStore/WatchAuditStore, read in-process against a mounted
# copy of vinu-screener's data root).
COPY vinu-screener /app/vinu-screener
RUN pip install --no-cache-dir -e /app/vinu-screener

# vinu-portfolio -- for E's concentration piece (AllocationHistoryStore,
# read in-process against a mounted copy of vinu-portfolio's data root).
COPY vinu-portfolio /app/vinu-portfolio
RUN pip install --no-cache-dir -e /app/vinu-portfolio

COPY vinu-reflection /app/vinu-reflection

WORKDIR /app/vinu-reflection

RUN pip install --no-cache-dir -e ".[dev]"

COPY vinu-reflection/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV VINU_REFLECTION_DATA_ROOT=/data
ENV VINU_REFLECTION_AGENT_DATA_ROOT=/agent-data
ENV PYTHONUNBUFFERED=1

VOLUME ["/data"]

ENTRYPOINT ["/app/entrypoint.sh"]
