# Phase 114: Every strategy, inside the user's own trading window

Run 2026-10-09. Code: [`phase114_my_window.py`](../phase114_my_window.py).
The user watches the 09:30 open without trading and mostly stops after
10:30–11:00 (their stated practice, fixed before this run). Each strategy's
first entry per day **inside 09:45–10:30** (and 09:45–11:00) was re-scored with
every management plan; the plan was chosen on 2023–24 and judged on 2025–26.

## 09:45–10:30, per year (FIXED management; R per trade after costs)

| Strategy | Mkt | 2023 | 2024 | 2025 | 2026 | 2025–26 with plan chosen on 2023–24 |
|---|---|---|---|---|---|---|
| **TJR 15m reversal (Ph111)** | **ES** | **+0.05** | **+0.10** | **+0.02** | **+0.02** | +0.02 (FIXED), CI −0.15…+0.20 |
| TJR 15m reversal | NQ | −0.01 | −0.07 | +0.08 | −0.13 | +0.02 (CUT) |
| Pullback IFVG, with morning (Ph108b) | NQ | −0.10 | −0.02 | −0.04 | +0.02 | **+0.00** (CUT_RUN) |
| Follow + 1h trend (Ph106) | NQ | −0.15 | +0.16 | +0.20 | −0.04 | −0.03 (RUN) |
| IFVG model (Ph107) | NQ | −0.06 | −0.17 | −0.10 | −0.06 | −0.03 (HALF_CUT) |
| Fade the sweep (Ph104) | NQ | −0.23 | −0.11 | −0.03 | −0.05 | −0.06 (RUN) |
| TJR liquidity model (Ph113) | NQ | +0.09 | +0.02 | −0.20 | −0.04 | −0.07 (RUN) |
| Pullback IFVG / IFVG model / follow / liquidity | ES | | | | | −0.10 … −0.13 |

**Verdict: no strategy passes**, but the user's window helps. Most results move
closer to zero than over the full morning.

**One watch-list item: ES · TJR 15-minute reversal, 09:45–10:30** is positive
in all four years (+0.05, +0.10, +0.02, +0.02; ~60–70 trades a year). The
effect is tiny and its 95% range includes zero. Among 24 market × window ×
strategy combinations, one all-positive row is about what chance would give.
It is the best candidate to **forward-track on paper**, rules unchanged.
