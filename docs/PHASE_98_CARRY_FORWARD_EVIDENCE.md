# Phase 98 — Funding-Carry Forward-Evidence Harness

**Status: COMPLETE (and now accumulating).** Read-only research. No
execution, no orders, no broker transmission, no account mutation, no
signals emitted. Frozen Phase-74 Gold holdout never read; live automation
disabled.

## Purpose

Phase 97 produced the research program's first non-null verdict —
`USABLE_EDGE_FOUND`: ~25% of capital in delta-neutral crypto funding
carry, rest in cash. Before any capital is risked, the disciplined step is
to accumulate **genuine real-time forward evidence** — does the edge keep
behaving the way the 2017–2026 backtest says it should, on weeks the
backtest never saw?

This phase is that harness. It is a **weekly-run shadow ledger**, not a
trader.

## What it does

1. *(optional `--refresh`)* re-runs the idempotent Phase 94/96 crypto data
   ingestion so the forward window can grow.
2. Runs the **frozen** Phase-96 carry rules over all history and splits the
   weekly result at a frozen **go-live anchor (2026-09-04)** — the last
   Friday with complete data at phase creation. Weeks `<=` anchor are the
   *backtest reference*; weeks strictly after are *forward* (real-time
   out-of-sample) evidence.
3. Applies Phase 97's frozen **f\* = 25%** carry sizing to the forward
   returns → the recommended book's real forward equity curve.
4. Appends an **immutable, timestamped snapshot** each run
   (`phase98_forward_snapshot__<iso>` artifacts, never overwritten); the
   running index lives in the main Phase-98 artifact.
5. Once **≥ 12 forward weeks** exist, compares the forward segment to the
   backtest reference and issues a verdict.

Nothing is fitted or tuned — every rule and threshold is frozen and
inherited from Phase 96/97.

## Verdict states

| Verdict | Condition |
|---|---|
| `FORWARD_EVIDENCE_INSUFFICIENT` | < 12 forward weeks — keep accumulating |
| `FORWARD_EVIDENCE_DIVERGING` | forward funding < 25% of backtest, **or** forward Sharpe < 0 — do not deploy, re-examine the thesis |
| `FORWARD_EVIDENCE_TRACKING` | forward funding ≥ 60% of backtest **and** forward Sharpe ≥ 0.5 |
| `FORWARD_EVIDENCE_CONFIRMING` | tracking **and** ≥ 26 forward weeks — the Phase-97 edge is being confirmed in real time |

## Current state (at commit)

| | |
|---|---:|
| go-live anchor | 2026-09-04 |
| data through | 2026-09-11 |
| backtest reference | 473 weeks, ann funding +10.6%, Sharpe 2.9 |
| forward evidence | **1 week** — accumulating |
| verdict | `FORWARD_EVIDENCE_INSUFFICIENT` |

The harness now needs to be re-run weekly (with `--refresh`) so the
forward window grows. A meaningful read is ~3 months out (12 weeks); a
confirming read is ~6 months (26 weeks).

## Determinism

`determinism.match == True` (the ledger split is a pure function of the
data and the frozen anchor).

## API

`GET /api/research/funding-carry-forward` — the latest persisted result
(backtest reference, forward evidence, recommended-book forward equity,
verdict, snapshot history). GET-only; `NOT_COMPUTED` until
`python -m phase98_carry_forward_evidence` has run.

## Operating it

Manually:

```
python -m phase98_carry_forward_evidence --refresh
```

Each run ingests the past week's crypto data, extends the forward ledger,
appends a snapshot, and updates the verdict. When the verdict reaches
`FORWARD_EVIDENCE_CONFIRMING`, the Phase-97 allocation has a real
out-of-sample track record and can be considered for a small live
allocation. If it ever reads `FORWARD_EVIDENCE_DIVERGING`, stop.

### Automating the weekly run

`phase98_forward_daemon.py` is a thin scheduler wrapper (no strategy
logic, no execution). It decides *when* to call the harness and logs the
outcome to `phase98_daemon_log.txt`.

- `python phase98_forward_daemon.py --once` — run the harness **iff** a
  weekly run is due (≥ 7 days since the last snapshot), then exit.
- `python phase98_forward_daemon.py --loop` — run forever, checking every
  6 hours.
- `python phase98_forward_daemon.py --status` — print whether a run is due.

**Windows Task Scheduler** (recommended — survives reboots, no terminal):

```
powershell -ExecutionPolicy Bypass -File register_phase98_weekly.ps1
```

This registers a task that runs `--once` **daily at 10:00**; the daemon's
internal 7-day gate means the harness itself only actually runs once a
week, and a missed day (laptop asleep) is caught up on the next trigger.

Remove it with:
```
Unregister-ScheduledTask -TaskName "TradeLogger Phase98 Forward Evidence" -Confirm:$false
```

## Next

- **Phase 99 — FX / rate-differential carry** (a second uncorrelated
  sleeve, once a multi-country short-rate source / `FRED_API_KEY` is
  available), folded into the Phase-97 allocation.
