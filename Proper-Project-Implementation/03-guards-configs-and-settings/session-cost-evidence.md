# Session cost base: what the published figures say

Written 2026-10-08 for problem log O10 and P45. The backtest charges slippage and spread more outside the regular session. The multipliers (`VINU_SIM_SESSION_COST_MULT`) are taken from the published figures below. They are a base, to be refined by our own quote recorder (`/stock/spread-stats`).

## The base now in use

| Session | Multiplier | Why |
|---|---|---|
| regular | 1 | the reference |
| pre-market (04:00 to 09:30 New York) | 5 | no direct figure found; the middle of the 4 to 10 times band reported for extended hours |
| after-hours (16:00 to 20:00) | 7 | measured: 58.1 bps against 8.4 bps in regular trading, about 6.9 times |
| overnight (20:00 to 04:00) | 3 | about 3 times regular for stocks that trade consistently overnight on Blue Ocean |

The multiplier scales only the slippage and spread part of a trade's cost (default slippage 0.0005, so 5 bps a side in regular hours), not the commission. After-hours at 7 gives about 35 bps a side, close to half of the 58 bps quoted spread, which is the right order of magnitude.

## What the sources say

Figures come from search-result summaries, not from reading the full papers (the arXiv PDF was too large to fetch). Treat them as rough.

- **After-hours.** "The average quoted spread during post-close (after-hours) trading is 58.1 basis points, while the average spread in regular trading equals 8.4 basis points", about seven times. On days without announcements the median quoted spread starts at 5 bps at the end of the regular session, then rises to 30 to 35 bps within the first five minutes after the close and keeps rising. Source: [Warp speed price moves: Jumps after earnings announcements (arXiv 2601.08962)](https://arxiv.org/pdf/2601.08962). The sample is built around earnings announcements, so it may lean high.
- **Extended hours, general.** "Median spreads in after-hours markets are quite stable, mostly falling in a range of four to ten times the spreads in the regular session." An older study found the 250 highest-volume Nasdaq stocks trading outside regular hours at an average spread of 0.48 percent. Found through the same search; the original paper was not opened.
- **Overnight (Blue Ocean ATS, 20:00 to 04:00).** For securities that trade consistently overnight, quoted spreads are about three times those of regular hours; less active stocks show 10 to 20 times, with thinner books. Another summary says the overnight spreads are comparable to extended hours and roughly twice regular hours, so the evidence is mixed. Sources: [BMLL, how much liquidity is available during overnight trading](https://www.bmlltech.com/news/market-insight/there-is-a-clear-trend-towards-24-7-equity-trading-but-how-much-liquidity-is-available-for-participants-during-overnight-trading), [Eaton paper](https://haslam.utk.edu/wp-content/uploads/2024/11/Eaton-Paper.pdf).
- **Brokers.** Alpaca, Robinhood and Interactive Brokers all route overnight orders to the same venue (Blue Ocean ATS), so the venue's spread, not the broker's, sets the cost; the broker adds no spread of its own on commission-free plans. See [Alpaca 24/5 trading](https://docs.alpaca.markets/us/docs/245-trading).

## What this does not cover

- Thin stocks: the overnight 3 is for names that trade consistently. A thin name can cost 10 to 20 times more. The backtest has no per-name liquidity scaling for this, so overnight results for thin names are still flattered.
- Our own quotes: the recorder reads an IEX-only feed, which shows a median of about 31 bps even in the regular session, far above the national best bid and offer. Its absolute level is not usable; only its ratio between sessions may be.
- Time of day inside a session: spreads widen right after the close and narrow later in a session. One multiplier per session ignores that.

## How to change it

Set `VINU_SIM_SESSION_COST_MULT` (for example `premarket=5,regular=1,afterhours=7,overnight=3`). A guard test pins the defaults, so changing them in code means changing this file too.
