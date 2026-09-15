# Killzone Scanner — TradingView port

A Pine Script v5 port of `killzone_scanner.py` (the Killzone Scanner in the
TradeLogger app) so the same sweep + market-structure-shift ("MSS") idea can
be backtested with TradingView's own Strategy Tester, on TradingView's full
history, instead of trusting the web app's numbers on faith.

## How to use it

1. Open any chart on tradingview.com.
2. Open the **Pine Editor** (bottom panel, or the "Pine Editor" tab).
3. Delete the placeholder script, paste in the full contents of
   `killzone_scanner.pine`.
4. Click **Add to chart**.
5. Open the **Strategy Tester** tab (next to the chart) to see trades, equity
   curve, win rate, profit factor, etc. — same as any other Pine strategy.
6. Every threshold is an input (gear icon on the strategy in the chart's
   top-left, or right-click → Settings → Inputs) — swing lookback, minimum
   displacement, max bars from sweep to shift, the killzone filter, and the
   backtest target's risk multiple. Nothing is hardcoded.

## Changing risk per trade

**Settings (gear icon) → Inputs → "Risk % of equity per trade"** (under the
Backtest group). This sizes each trade so that if the stop is hit, the loss
is exactly that % of your *current* equity — not a flat number of
units/contracts. Raising it doesn't change which trades fire, only how big
each one is, so it scales total return **and** drawdown together (2% risk
roughly doubles both compared to 1%, since every trade is now twice the
size). Try 0.5%, 1%, and 2% on the same date range and compare total PnL
against max drawdown, not just the PnL number alone — a bigger number that
also has a much deeper drawdown isn't necessarily an improvement.

## Seeing the entry/stop/target, not just the sweep+MSS shapes

Every candidate draws three lines (yellow = entry, red = stop, green =
target) plus labels, extending `planLineBars` bars to the right — this
happens **regardless of `enableBacktest`**, so turning backtesting off still
shows you the full plan each candidate would have used, not just the bare
sweep/MSS shapes. TradingView also auto-draws its own small entry/exit
arrows when `enableBacktest` is on and an order actually filled (standard
Strategy Tester behaviour) — those are separate from, and in addition to,
these explicit lines.

## What matches the web app, and what doesn't

This is a **port, not a byte-identical copy**. The parts that define what
counts as a candidate at all are the same:

- Swing points: `ta.pivothigh`/`ta.pivotlow` confirm a swing the same
  "N bars each side" way `killzone_scanner.py`'s rolling-window detector does.
- A **sweep** = a wick clears a confirmed swing, then the candle closes back
  through it.
- A **structure shift (MSS)** = a close beyond the *opposing* swing, with a
  candle body at least `minDispATRMult` × ATR — real displacement, not a wick
  poke.
- A **candidate** = an MSS paired with the nearest prior opposing-direction
  sweep, within `maxBarsAfterSweep` bars.
- The killzone windows (London / NY AM / NY PM) use the exact same New York
  clock-time windows as `killzone_scanner.py`'s `_killzone_for_timestamp`.

The one real difference: the web app's `potential_target` is the nearest
*real, untapped liquidity pool* from `calculate_liquidity_zones()`
(`market_data.py`) — Pine has no equivalent to that computation available
here, so this script's backtest target is instead a plain risk-multiple (the
`rrMultiple` input) away from entry, which is the normal way a Pine strategy
sizes a target. **Expect this script's exact win rate / P&L to differ from
what the web app's Killzone Scanner shows for that reason** — the entry/stop
logic (the part that actually defines whether something is a candidate at
all) is the same; only the target/exit rule differs.

## What this is not

A backtest, a pattern-flagging tool, or a strategy — however good the
Strategy Tester numbers look — is not investment advice and is not a claim
that this trades profitably in real markets. Overfitting a strategy to one
symbol/timeframe's history is easy to do by accident; if you tune the inputs
to make the backtest look better, test the result on a different symbol or a
different chunk of history before trusting it. Running this live is your own
decision, entirely outside TradeLogger — there is no execution path from the
web app to this script or back.
