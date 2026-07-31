# System Architecture

Definition-phase reference diagram — reflects `vinu-components/docker-compose.yml`
as of 2026-07-31. See [full-plan.md](full-plan.md) for the validation plan
this supports, and [scope-responsibilities/](scope-responsibilities/) for
per-component detail.

## Service dependency graph

```mermaid
graph TD
    Alpaca[("Alpaca Markets API<br/>(trading / market-data / news)")]

    subgraph Data["Data & Feature Layer"]
        stock["vinu-stock-price<br/>:8081<br/>1min candles → 1d/4h/1h/15m"]
        news["vinu-news<br/>:8080<br/>news ingestion + enrichment"]
        tools["vinu-tools (features-api)<br/>:8082<br/>technical/alpha features"]
        analysis["vinu-initial-analysis<br/>:8083<br/>news/price correlation"]
    end

    subgraph Decision["Strategy & Simulation Layer"]
        strategy["vinu-strategy<br/>:8084<br/>YAML strategies → weights"]
        simulator["vinu-simulator<br/>:8085<br/>backtest engine"]
        research["vinu-research<br/>:8087<br/>strategy generation/refinement"]
    end

    subgraph Orchestration["Portfolio & Execution Layer"]
        portfolio["vinu-portfolio<br/>:8090<br/>unified allocation + game plan + risk"]
        agent["vinu-agent<br/>:8086<br/>LLM agent + skills + broker"]
        live["vinu-live<br/>:8091<br/>trade execution (Stage 2+)"]
    end

    Alpaca -->|candles| stock
    Alpaca -->|articles| news

    stock --> tools
    stock --> analysis
    news --> analysis

    tools --> strategy
    analysis --> strategy
    stock --> simulator
    strategy --> simulator
    tools --> simulator

    tools --> research
    analysis --> research
    stock --> research
    simulator --> research

    strategy --> portfolio
    research --> portfolio
    simulator --> portfolio
    analysis --> portfolio
    stock --> portfolio

    stock --> agent
    tools --> agent
    news --> agent
    analysis --> agent
    strategy --> agent
    simulator --> agent
    research --> agent

    portfolio --> live
    agent --> live
    stock --> live
    Alpaca -.->|paper orders, Stage 2+| agent

    classDef stage1 fill:#2b6cb0,color:#fff,stroke:#1a365d
    classDef stage2 fill:#718096,color:#fff,stroke:#2d3748,stroke-dasharray: 4 3
    classDef external fill:#38a169,color:#fff,stroke:#22543d

    class stock,news,tools,analysis,strategy,simulator,research,portfolio stage1
    class agent,live stage2
    class Alpaca external
```

**Legend:** blue = in scope for Stage 1 (historical validation, this
document's focus). Grey/dashed = Stage 2+ only (paper/live trading),
explicitly deferred. Green = external data source.

## Stage 1 execution flow (historical simulation)

```mermaid
sequenceDiagram
    participant U as Operator
    participant SP as vinu-stock-price
    participant FT as vinu-tools
    participant NW as vinu-news
    participant IA as vinu-initial-analysis
    participant ST as vinu-strategy
    participant SM as vinu-simulator
    participant RS as vinu-research
    participant PF as vinu-portfolio

    U->>SP: fetch 1min candles (2022-01-01 to 2026-06-30)
    SP->>SP: aggregate to 1d / 4h / 1h / 15m
    U->>NW: fetch historical news (best-effort coverage)
    par Feature & correlation prep
        FT->>SP: request candles
        FT->>FT: compute technical/alpha features
        IA->>NW: request articles
        IA->>SP: request candles
        IA->>IA: compute correlation/impact
    end
    U->>ST: evaluate strategy YAMLs (easy / medium / complex)
    ST->>FT: request features
    ST->>IA: request correlation context
    ST-->>U: target weights per rebalance point
    U->>SM: POST /simulate (per strategy)
    SM->>ST: fetch weights
    SM->>SP: fetch prices
    SM-->>U: Sharpe, drawdown, win rate, Calmar, baseline comparison
    U->>RS: complex-tier strategy generation (LLM-assisted)
    RS->>FT: features
    RS->>SM: backtest candidate
    RS-->>U: strategy artifact recorded
    U->>PF: historical-simulate --days N
    PF->>ST: fetch strategies
    PF->>SP: fetch returns
    PF-->>U: unified allocation result (risk-parity + regime tilt only)
    Note over U,PF: Stage 1 output: real Sharpe/drawdown/win-rate numbers,<br/>go/no-go input for Stage 2
```

## Notes on scope boundaries

- `vinu-live` and `vinu-agent`'s broker layer are drawn but **not
  exercised** in Stage 1 — see
  [scope-responsibilities/vinu-live.md](scope-responsibilities/vinu-live.md)
  and
  [scope-responsibilities/vinu-agent.md](scope-responsibilities/vinu-agent.md).
- The dependency arrows mirror `docker-compose.yml`'s `depends_on` chains
  exactly — this is the real current topology, not an aspirational one.
- `vinu-portfolio` is drawn as calling `vinu-stock-price`,
  `vinu-strategy`, `vinu-simulator`, `vinu-initial-analysis` directly (per
  its `config.py`), on top of the docker-compose `depends_on` set
  (`strategy-api`, `research-api`, `simulator-api`) — the extra edges
  reflect what its code actually calls at runtime, not just container
  startup ordering.
