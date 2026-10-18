# -*- coding: utf-8 -*-
"""
Trade insights for the Analytics page — the "TradeZella-style" reports:
when you trade best (day of week / hour / holding time), what breaking your
own rules costs, and streaks / best and worst day.

Pure and read-only: it takes the already account/symbol/date-filtered
closed-trade population the `/performance` route built (one row per
position, times naive UTC) and only groups and counts it. No metric formula
from `analytics.py` is reimplemented here.

Timezone: day-of-week and hour use the trade's ENTRY time converted to the
viewer's timezone (the browser sends its IANA name), because "I trade badly
after 9pm" only means something on your own clock. Best/worst day and the
day streaks use the exit date exactly as the calendar's `daily_pnl` does, so
they agree with the calendar.
"""
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from api.schemas import (
    DayExtreme,
    InsightBucket,
    RulesRow,
    StreakStats,
    TradeInsights,
)

# The one-tap journal answers (frontend/src/components/journal/reviewOptions.ts QUICK_TAGS).
RULE_TAGS = ("By my rules", "Bent my rules", "Rushed")
NOT_MARKED = "Not marked"

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# (key, label, upper bound in minutes — exclusive)
HOLD_BUCKETS = (
    ("lt5m", "Under 5 min", 5),
    ("5_15m", "5–15 min", 15),
    ("15_60m", "15–60 min", 60),
    ("1_4h", "1–4 hours", 240),
    ("4_24h", "4–24 hours", 1440),
    ("gt1d", "Over a day", float("inf")),
)


def resolve_tz(name: Optional[str]) -> str:
    """A valid IANA zone name, or "UTC" when missing / unknown."""
    if name:
        try:
            ZoneInfo(name.strip())
            return name.strip()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return "UTC"


def _bucket(key: str, label: str, g: pd.DataFrame) -> InsightBucket:
    return InsightBucket(
        key=key,
        label=label,
        trades=int(len(g)),
        wins=int((g["net_profit"] > 0).sum()),
        net_profit=round(float(g["net_profit"].sum()), 2),
    )


def _empty_bucket(key: str, label: str) -> InsightBucket:
    return InsightBucket(key=key, label=label, trades=0, wins=0, net_profit=0.0)


def _local_entry(df: pd.DataFrame, tz: str) -> pd.Series:
    when = df["entry_time"] if "entry_time" in df.columns else df["exit_time"]
    when = when.fillna(df["exit_time"])
    return when.dt.tz_localize("UTC").dt.tz_convert(tz)


def _hold_minutes(df: pd.DataFrame) -> pd.Series:
    if "duration_minutes" in df.columns:
        mins = pd.to_numeric(df["duration_minutes"], errors="coerce")
    else:
        mins = pd.Series([float("nan")] * len(df), index=df.index)
    if "entry_time" in df.columns:
        derived = (df["exit_time"] - df["entry_time"]).dt.total_seconds() / 60.0
        mins = mins.where(mins.notna() & (mins > 0), derived)
    return mins


def _rules(df: pd.DataFrame) -> List[RulesRow]:
    tags = df["setup_tag"].fillna("").astype(str).str.strip() if "setup_tag" in df.columns else pd.Series([""] * len(df), index=df.index)
    canon = {t.lower(): t for t in RULE_TAGS}
    labelled = tags.str.lower().map(canon).fillna(NOT_MARKED)
    rows = []
    for tag in (*RULE_TAGS, NOT_MARKED):
        g = df[labelled == tag]
        n = int(len(g))
        net = round(float(g["net_profit"].sum()), 2) if n else 0.0
        rows.append(RulesRow(
            tag=tag, trades=n, wins=int((g["net_profit"] > 0).sum()) if n else 0,
            net_profit=net, avg_per_trade=round(net / n, 2) if n else 0.0,
        ))
    return rows


def _run_lengths(signs: List[int]) -> Dict[str, int]:
    """Longest +1 run, longest -1 run, and the run the list ends on (0 breaks a run)."""
    best_up = best_down = cur = 0
    cur_sign = 0
    for s in signs:
        if s != 0 and s == cur_sign:
            cur += 1
        else:
            cur_sign, cur = s, (1 if s != 0 else 0)
        if cur_sign > 0:
            best_up = max(best_up, cur)
        elif cur_sign < 0:
            best_down = max(best_down, cur)
    return {"up": best_up, "down": best_down, "cur_sign": cur_sign, "cur": cur}


def _kind(sign: int) -> str:
    return "win" if sign > 0 else "loss" if sign < 0 else "none"


def _streaks(df: pd.DataFrame) -> StreakStats:
    ordered = df.sort_values(by="exit_time")
    trade_signs = [1 if v > 0 else -1 if v < 0 else 0 for v in ordered["net_profit"]]
    t = _run_lengths(trade_signs)

    daily = ordered.groupby(ordered["exit_time"].dt.date)["net_profit"].sum().sort_index()
    day_signs = [1 if v > 0 else -1 if v < 0 else 0 for v in daily]
    d = _run_lengths(day_signs)

    best = worst = None
    if not daily.empty:
        best_date, worst_date = daily.idxmax(), daily.idxmin()
        best = DayExtreme(date=best_date.isoformat(), net_profit=round(float(daily[best_date]), 2))
        worst = DayExtreme(date=worst_date.isoformat(), net_profit=round(float(daily[worst_date]), 2))

    return StreakStats(
        current_kind=_kind(t["cur_sign"]), current_count=t["cur"],
        longest_win=t["up"], longest_loss=t["down"],
        current_day_kind=_kind(d["cur_sign"]), current_day_count=d["cur"],
        longest_green_days=d["up"], longest_red_days=d["down"],
        green_days=sum(1 for s in day_signs if s > 0),
        red_days=sum(1 for s in day_signs if s < 0),
        best_day=best, worst_day=worst,
    )


def build_insights(filtered: pd.DataFrame, tz_name: Optional[str] = None) -> TradeInsights:
    tz = resolve_tz(tz_name)
    if filtered is None or filtered.empty:
        return TradeInsights(
            timezone=tz,
            by_weekday=[_empty_bucket(str(i), w) for i, w in enumerate(WEEKDAYS)],
            by_hour=[_empty_bucket(str(h), f"{h:02d}:00") for h in range(24)],
            by_hold=[_empty_bucket(k, label) for k, label, _ in HOLD_BUCKETS],
            open_unknown=0,
            rules=_rules(pd.DataFrame({"net_profit": pd.Series(dtype=float)})),
            streaks=_streaks(pd.DataFrame({"exit_time": pd.Series(dtype="datetime64[ns]"), "net_profit": pd.Series(dtype=float)})),
        )

    df = filtered.copy()

    # A trade whose open was never seen (Capital.com's older-history import only gets the closing
    # record, so it stores the close time as the open and a 0 holding time) has no real open hour,
    # weekday or holding time. Don't guess: leave it out of all three and say how many.
    mins = _hold_minutes(df)
    known = mins.notna() & (mins > 0)

    local = _local_entry(df, tz)
    df["_dow"] = local.dt.dayofweek
    df["_hour"] = local.dt.hour
    opened = df[known]
    by_weekday = [_bucket(str(i), w, opened[opened["_dow"] == i]) for i, w in enumerate(WEEKDAYS)]
    by_hour = [_bucket(str(h), f"{h:02d}:00", opened[opened["_hour"] == h]) for h in range(24)]

    by_hold = []
    lower = 0.0
    for key, label, upper in HOLD_BUCKETS:
        by_hold.append(_bucket(key, label, df[known & (mins >= lower) & (mins < upper)]))
        lower = upper

    return TradeInsights(
        timezone=tz,
        by_weekday=by_weekday,
        by_hour=by_hour,
        by_hold=by_hold,
        open_unknown=int((~known).sum()),
        rules=_rules(df),
        streaks=_streaks(df),
    )
