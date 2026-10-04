# How does the system find new analogies?

Vision: *"market memory: 'this looks like 37 past situations: 23 up, 14 down, average +1.3%, worst drawdown −2.8%'"* and *"research machine: learn where the edge holds and fails"* (`../vision-trding-system.md` A13, A16). "Analogy" means two different things in this system, and they work differently: **recognising** a situation that resembles earlier ones (market memory), and **discovering** a pattern or idea nobody told it to look for. Both are checked.

---

## Q1. Can it recognise "this looks like earlier situations", and say what happened after them?

**Verdict: WORKS, WITH A LIMIT.**

`trend_lifecycle/patterns.py`: every peak the angle detects is stored with 18 features (RSI, ATR%, distance from moving averages, volume ratios, run-up bars, wick and body size, ...) and what happened after it (drawdown, bars to recover). For a new peak: z-score the features with the library's own mean and spread, then rank the library by cosine similarity and return the nearest `k` (5), each with its similarity, its drawdown and its recovery time. The library grows by itself: every run reads all stored snapshots, de-duplicates by bar time and keeps the peaks. Rules that keep it honest: only peaks **strictly before** the query bar may match (walk-forward, no look-ahead); a session filter applies only if at least 10 same-session candidates remain (so a small library is never starved); a bad or empty query returns no analogue instead of a guess.

**Worked example** (`vinu-initial-analysis/tests/test_logic_analogues_by_hand.py`, 6 tests, mutation-checked: removing the time filter fails two). Library of six earlier peaks, three "hot" (RSI 80-85, ATR 1.0-1.2%, run-up 28-34 bars) and three "calm" (RSI 40-45, ATR 4-5%, run-up 4-6). Today's peak is hot (RSI 83, ATR 1.1%, run-up 31).

| Question | Expected by hand | Result |
|---|---|---|
| nearest 3 analogues | the three hot peaks (bar times 1000, 2000, 3000), similarity > 0.9 | **yes** |
| what happened after the 2000 peak | drawdown −7.5%, recovered in 15 bars, carried with the match | **yes** |
| order | best first; the hot three before the calm three | **yes** |
| today is at bar time 2500 | only 1000 and 2000 existed; 3000 is the future and is excluded even though it is the best match | **yes** |
| nothing earlier than today | no analogue, not a guess | **yes** |
| unusable query (NaN, unknown feature) | nothing | **yes** |

**The limit, against the vision's own example.** The vision's picture is an *aggregate* over many analogues ("37 situations, 23 up / 14 down, average +1.3%, median +0.9%, worst −2.8%"). The code returns the 5 nearest peaks one by one, with their **drawdown and recovery time** (what a peak is followed by), not a win/lose count or an average return. There is no summary line, and the live-decision context does not include analogues at all: they reach an agent only through the stored angle rows. Cosine similarity compares the *direction* of the feature vector, so a mild hot setup and an extreme one with the same shape rank as equally similar (the size of the deviation is ignored). This library is persisted and must stay comparable over time, so I did not change it (see **D7**).

**Waits for data:** how useful the nearest-5 are depends on how many peaks the library holds for a ticker.

---

## Q2. Can it notice a pattern nobody asked it to watch for?

**Verdict: WORKS (the noticing), GAP (acting on it).**

* **Track 2 move detection** (`detector.detect_move`): on **every** candle of every watched (ticker, timeframe), whether or not any must-condition fired, a move is "real" when the last close changed by more than 2 × ATR(14). Worked example: ATR 2.0 → threshold 4.0; a close going 100 → 105 is a move up (5 > 4), 100 → 103 is not, fewer than 2 bars or no ATR yet returns `None` ("cannot tell yet", never "quiet"). Detections are stored (`MoveEvidenceStore`) with no strategy attached.
* **Unconfirmed moves** (`list_unconfirmed_moves`): real moves for which no recorded must-condition trigger exists in the same window. They are shown to the deciding agent as corroboration or as "something nobody was watching".
* **What nothing does:** an unconfirmed move is never fed to the idea generator, so the system notices "AAPL moved 3 ATR and none of my conditions saw it" and the research loop never hears about it (**D8**).

---

## Q3. How do new ideas and strategies arise, and how does it avoid re-finding the old ones?

**Verdict: WORKS, WITH A LIMIT.**

| Step | What it does | Check |
|---|---|---|
| Where candidates come from | the screener ranking supplies tickers; the planner-worker triages them (cap 3 candidates per ticker per week); a human can hand in a raw theory or analogy through the thesis-intake team (no code, checked against real evidence first) | connection verified (routing work) |
| Drafting | three candidate strategies per call, with the latest evidence for that idea shown in the prompt | wired |
| Not repeating itself | TF-IDF similarity first, then one LLM tie-break ("SMA" vs "moving-average" = same idea; shared words but different ideas ≠ same); the graveyard keeps every discarded draft, sweep loser and rejected hypothesis, queryable by ticker | tests exist (`idea_similarity`, graveyard) |
| Learning across ideas | evidence pooled by indicator across strategies (`GET /research/indicators/pool`: "this indicator, in all strategies that used it, did this") | a human view: **nothing reads it** (routing work, class `human-view`) |

**Limit:** the pooled-by-indicator evidence and the graveyard are visible to a person but, apart from the duplicate check, do not steer the next draft. Whether they should is a design question that waits for enough finished research runs to be worth pooling.

---

## Q4. Findings and decisions raised here

* **D7 (market-memory output).** Should the analogue output grow into the vision's summary (count up / down, average and median forward return, worst drawdown over the matched peaks) and be included in the live-decision context? Options in `00`.
* **D8 (unconfirmed moves → ideas).** Should recent unconfirmed moves be handed to the idea generator? Options in `00`.
