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

## Realistic leverage, not unlimited leverage

TradingView's paper trading enforces no margin limit by default. On a pair
with a tight stop (like USDJPY), risk-based sizing can — and did, verified
against a real backtest — call for a position worth **millions of dollars
on a $5K account**. The arithmetic is correct (that position really would
lose exactly 1% if the stop hit), but no real broker would ever fund it.
**"Max account leverage"** (Backtest group) caps position size to what your
actual leverage allows; when a trade's risk-sized quantity would need more
than that, it's capped instead, so realized risk on very tight stops may
come in under your risk % — that's the honest, fundable number. Set it to
match what your real broker actually offers (many retail forex brokers cap
at 30:1 in regulated regions, higher elsewhere) before trusting a backtest
as something you could actually place.

## Currency conversion across symbols (automatic)

`syminfo.pointvalue × riskDist` gives a trade's risk in the **symbol's quote
currency**, which isn't always your account's. `quoteToAccount()` derives that
rate from the symbol rather than assuming it, so switching pairs needs no code
edit:

| Symbol (USD account) | Quote | Rate applied |
|---|---|---|
| EURUSD, GBPUSD, AUDUSD, **XAUUSD** | USD | 1 — no conversion |
| USDJPY, USDCAD, USDCHF | JPY / CAD / CHF | `1 / close` |
| EURJPY, GBPJPY (crosses) | JPY | **none — refuses to trade** |

This used to be hardcoded as a bare `* close` for JPY pairs, which silently
oversized every position on any symbol already quoted in the account currency.
On XAUUSD at ~4,288 that multiplied size by 4,288×, drove equity negative, and
TradingView rejected the resulting negative `qty` outright
(`Invalid 'qty' value (-8624.2)`) — the backtest simply wouldn't run.

A **cross pair** (neither side is your account currency) genuinely can't be
converted from one chart without a second data feed, so the script places no
orders and prints a red label saying why — an empty Strategy Tester with no
explanation looks identical to "the strategy found no trades," which would be a
silently wrong conclusion. Sizing is also floored at zero, so a blown account
produces no order rather than a negative quantity.

Still worth running the List-of-Trades check below after switching symbols —
automatic isn't the same as verified.

## The two optional confluence filters (both default OFF)

Added because they're the two things most often suggested to "fix" a sweep+MSS
strategy that isn't working. Both are real implementations, and both default to
off so the baseline stays exactly what it was — **turn one on, re-run the same
date range, and compare against the baseline you already have.** Adding filters
until a backtest looks good is the single easiest way to overfit, which is what
the out-of-sample table above exists to catch.

**Fib / OTE entry** (`useFibFilter`). This one is not a filter, it's a
*different entry mechanic*: instead of a market order the instant the MSS
confirms, it places a **limit order** back inside the retracement zone of the
sweep→breakout leg (`fibLevel`, default 0.705 — the midpoint of the classic
61.8%–79% "optimal trade entry" zone) and waits for price to pull back into it.
If price never retraces, the order never fills and is cancelled after
`oteMaxWaitBars`. Expect **fewer trades with better R:R per trade** — whether
that nets out better is exactly what you're testing. A market entry at the
breakout and a limit entry at a retracement are two different strategies, so
compare them as such.

**Fixed Range Volume Profile** (`useVpFilter`). Builds a volume histogram over
the trailing `vpLookback` bars, buckets it into `vpBins` price levels, finds the
point of control (highest-volume bucket), and only allows the trade if entry
sits within `vpTolerance` × ATR of it. **The forex caveat matters here:**
TradingView's `volume` on spot FX is the broker's *tick count*, not real traded
volume — spot FX has no central tape, so no feed can report true volume. A
profile built from it shows where price spent active time, not where
institutional size traded, which is what people assume they're reading. This
project's own research tested tick-volume filters on FX pairs directly and found
they generally didn't help and sometimes hurt. This filter is likely more
meaningful on instruments with genuine reported volume (futures, crypto) than on
FX.

## The real research process: development → out-of-sample → forward test → live

A single backtest number, however good, tells you almost nothing on its
own — it's easy for an AI (or a human) to hand-tune a strategy's inputs
until one specific stretch of history looks great, which proves the
strategy fits *that data*, not that it has a real edge. The process this
project's own research always follows, applied here:

1. **Development** — pick a chunk of history (say, everything before a
   cutoff date) and freely adjust inputs (swing lookback, displacement,
   R:R, risk%) against it. This is the only period you're allowed to tune
   against.
2. **Freeze the inputs.** Stop touching them.
3. **Out-of-sample** — check performance on data *after* that cutoff, which
   the inputs were never tuned against. The script now does this
   automatically: set **"Out-of-sample starts"** (Settings → Inputs →
   Out-of-sample check) to your development/test split date, and a table in
   the top-right of the chart shows trades / win rate / profit factor for
   each half side by side. **If you see a bad out-of-sample number and
   change an input in response, you have just made that data part of
   development too** — the whole point is that this column stays untouched
   by tuning.
4. **Forward test** — once out-of-sample looks reasonable, run it live on
   paper trading (no real money) for a while going forward, on data that
   didn't exist when you built the script at all.
5. **Live** — only after all three hold up, and only ever with your own
   judgment about the risk, entirely outside TradeLogger.

Rough bar to clear before trusting a result enough to forward-test it (this
project's own research uses a similar bar elsewhere): at least ~200 trades
combined, profit factor comfortably above 1 in **both** the in-sample and
out-of-sample columns (not just in-sample), and a max drawdown you'd
actually be willing to sit through in real money — not just tolerable on
paper.

**A limitation to know**: TradingView strategies can't place live orders
directly through most brokers — real automation needs an alert plus a
separate execution bridge. That's consistent with this whole project's own
stance (no order path from the web app either); nothing here is meant to
become an automated live trader without you deliberately building that
separate piece yourself.

## Reading the results honestly

Two things to check beyond the headline win rate / profit factor before
trusting any run:

- **Average win/loss vs. your rrMultiple.** With a 2:1 target, a real
  stop-out should average close to -1R and a real win close to +2R (in
  whatever % terms Strategy Tester shows). If the average loss is much
  smaller than that, trades are being cut short before reaching their own
  stop — which used to happen here because a new opposite-direction signal
  reverses an open position immediately at the current price instead of
  waiting for that trade's actual exit. Fixed: a new entry is now only
  taken while flat (`strategy.position_size == 0`), so every trade plays out
  to its own stop or target first.
- **Long vs. Short performance separately** (Performance analysis →
  Breakdown → "By side"). If one side is carrying the whole result, that's
  a sign the test period simply trended in that direction — not that
  sweeps+MSS work symmetrically both ways, which is what the underlying
  idea actually claims. Test a period where the pair chopped or trended the
  other way before trusting a result that's really "long only, on an
  uptrend."

## Verify position sizing before trusting any result

Before reading anything into a backtest's PnL or drawdown, sanity-check that
risk is actually being sized correctly: open the **List of Trades** tab in
Strategy Tester, click on any *losing* trade, and check its P&L in dollars.
It should be roughly `riskPercent% × your account size` (e.g. ~$50 on a $5K
account at 1% risk) — if it's a tiny fraction of that (drawdown that looks
"too good to be true" is the tell), position sizing isn't actually risking
what you set, usually a currency/point-value quirk of that specific
instrument's data feed. This has already bitten this script twice (fixed by
using `syminfo.pointvalue`, then again by converting quote currency to
account currency) — it's cheap to re-check any time you switch symbols,
since different feeds can behave differently.

**Use the List of Trades' dollar P&L for this check, not the "Return %"
column or the Distribution tab's "Average loss/profit %"** — those are
computed relative to each trade's own position value (notional), not your
account equity, so they swing around a lot even when dollar risk per trade
is perfectly consistent. A trade risking exactly 1% of a $5K account will
always show close to -$50 in dollars, but its "Return %" might read -0.09%
on one trade and -0.52% on another purely because of how large that
particular trade's position happened to be — that's not a sizing bug, it's
just the wrong column to eyeball for this.

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
