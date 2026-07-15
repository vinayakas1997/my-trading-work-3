---
name: report-generate
description: Structured research report generation with template engine
category: analysis
---

## Report Generation

### Report Templates

#### Strategy Review
```markdown
# Strategy: {name}
- **Hypothesis**: {hypothesis}
- **Parameters**: {params}
- **IS Period**: {is_start} → {is_end}
- **OOS Period**: {oos_start} → {oos_end}

## Performance
| Metric | IS | OOS |
|--------|----|-----|
| Sharpe | {is_sharpe} | {oos_sharpe} |
| MaxDD | {is_maxdd} | {oos_maxdd} |
| Trades | {is_trades} | {oos_trades} |
| Profit Factor | {is_pf} | {oos_pf} |

## Equity Curve
{equity_chart}

## Diagnosis
{diagnosis}
```

#### Market Brief
- Macro context (rates, CPI, PMI, unemployment)
- Sector performance (top/bottom 3)
- Key levels (support/resistance for major indices)
- Risk events calendar

#### Factor Review
- Factor performance heatmap (IC by sector)
- Factor crowding score
- Regime classification
- Top/bottom decile portfolio stats

### Output Formats
- Markdown (default) — for chat display
- Run card — `run_card.md` + `run_card.json` for archiving
- PDF — for email distribution (requires wkhtmltopdf)
