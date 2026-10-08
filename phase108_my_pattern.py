"""Phase 108a — what the user's own NQ/ES trades have in common, measured.

Research only. For every closed NDX100/SPX500 position in the local MT5
account, measures the context at entry on 1-minute bars (New York time):

  mins_after_open     minutes from 09:30 to entry
  open_move           direction of the first 15 minutes (close 09:45 vs open 09:30)
  morning_move        direction from 09:30 to the minute before entry
  with_open_move      trade direction == open_move
  with_morning_move   trade direction == morning_move
  range_pct           where the entry sits in the 09:30 -> entry range (0 = low, 1 = high);
                      a short "in premium" is > 0.5, a long "in discount" is < 0.5
  pullback_inverted   in the 10 minutes before entry, a gap in the PULLBACK direction
                      (bullish gap before a short) was closed through within 3 minutes of entry
  swept_before        a live liquidity level on the side AGAINST the trade (a high before a
                      short) was breached between 09:30 and entry; which kind
  stop_vs_extreme     where the user's stop sits relative to the session extreme 09:30->entry
                      (high for shorts): + = beyond it (in points), - = inside it
  h1_bias_agrees      1-hour swing structure at 08:30 agrees with the trade
  attempt             1st, 2nd, 3rd... entry in the same direction that morning

    python -m phase108_my_pattern
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase104_tjr_selection as p4
import phase104b_my_trades as mt
import phase106_follow_sweep as p6


def features() -> pd.DataFrame:
    mine = mt.my_positions()
    p4.SESSION.clear()
    p4.SESSION.update(p6.INDEX_SESSION)
    data = {s: p1.load(s, "M1") for s in ("NQ", "ES")}
    rows = []
    for _, t in mine.iterrows():
        df = data[t["symbol"]]
        et = pd.Timestamp(t["entry_time"]).floor("min")
        day = et.normalize()
        o930 = df.loc[day + pd.Timedelta(hours=9, minutes=30):].iloc[0]["open"]
        c945 = df.loc[: day + pd.Timedelta(hours=9, minutes=44, seconds=59)].iloc[-1]["close"]
        seg = df.loc[day + pd.Timedelta(hours=9, minutes=30): et - pd.Timedelta(seconds=1)]
        side = int(t["side"])
        open_move = int(np.sign(c945 - o930))
        morning = int(np.sign(seg["close"].iloc[-1] - o930)) if len(seg) else 0
        hi, lo = (seg["high"].max(), seg["low"].min()) if len(seg) else (t["entry"], t["entry"])
        rng = hi - lo
        pct = (t["entry"] - lo) / rng if rng > 0 else 0.5
        # pullback gap inverted just before entry
        w = df.loc[et - pd.Timedelta(minutes=10): et]
        h, l, c = w["high"].to_numpy(), w["low"].to_numpy(), w["close"].to_numpy()
        inv = False
        for k in range(2, len(w)):
            if side < 0 and h[k - 2] < l[k]:      # bullish gap in the pullback before a short
                bottom = h[k - 2]
                inv = inv or any(c[q] < bottom for q in range(k + 1, len(w)) if len(w) - q <= 4)
            if side > 0 and l[k - 2] > h[k]:      # bearish gap before a long
                top = l[k - 2]
                inv = inv or any(c[q] > top for q in range(k + 1, len(w)) if len(w) - q <= 4)
        # liquidity swept against the trade between 09:30 and entry
        ctx = p4._daily_context(df[df.index < day + pd.Timedelta(days=1)])
        prev = [x for x in ctx.index if pd.Timestamp(x) < day][-1]
        lv = p4._levels(df, day, ctx, prev)
        t930 = day + pd.Timedelta(hours=9, minutes=30)
        swept = []
        for x in lv:
            if x["live_from"] > et:
                continue
            start = max(t930, x["live_from"])
            s2 = df.loc[start: et - pd.Timedelta(seconds=1)]
            if not len(s2):
                continue
            if side < 0 and x["side"] == "H" and s2["high"].max() > x["price"]:
                swept.append(x["family"])
            if side > 0 and x["side"] == "L" and s2["low"].min() < x["price"]:
                swept.append(x["family"])
        extreme = hi if side < 0 else lo
        stop_vs_ext = (t["sl"] - extreme) * (1 if side < 0 else -1) if t["sl"] == t["sl"] else np.nan
        rows.append({
            "trade": f"{t['symbol']} {et:%m-%d %H:%M} {'LONG' if side > 0 else 'SHORT'}", "profit": round(t["profit"], 1),
            "mins_after_open": int((et - t930).total_seconds() // 60), "with_open_move": side == open_move,
            "with_morning_move": side == morning, "range_pct": round(pct, 2),
            "premium_discount_ok": (side < 0 and pct > 0.5) or (side > 0 and pct < 0.5),
            "pullback_inverted": inv, "swept_before": ",".join(sorted(set(swept))) or "-",
            "stop_vs_extreme_pts": round(stop_vs_ext, 1) if stop_vs_ext == stop_vs_ext else None,
            "h1_bias_agrees": p4._h1_bias(df, day + pd.Timedelta(hours=8, minutes=30)) == side,
            "symbol": t["symbol"], "side": side, "day": str(day.date()),
        })
    out = pd.DataFrame(rows)
    out["attempt"] = out.groupby(["day", "symbol", "side"]).cumcount() + 1
    return out


def main(argv=None) -> int:  # pragma: no cover
    f = features()
    pd.set_option("display.width", 250)
    print(f.drop(columns=["symbol", "side", "day"]).to_string(index=False))
    win = f["profit"] > 0
    print("\nshare of trades with each trait (all / winners / losers):")
    for col in ("with_open_move", "with_morning_move", "premium_discount_ok", "pullback_inverted", "h1_bias_agrees"):
        print(f"  {col:<22} {f[col].mean():.0%}  /  {f[win][col].mean():.0%}  /  {f[~win][col].mean():.0%}")
    print(f"  swept a level first      {(f.swept_before != '-').mean():.0%}  /  {(f[win].swept_before != '-').mean():.0%}  /  {(f[~win].swept_before != '-').mean():.0%}")
    print(f"  minutes after open: median {f.mins_after_open.median():.0f} (range {f.mins_after_open.min()}-{f.mins_after_open.max()})")
    print(f"  stop beyond the morning extreme: {(f.stop_vs_extreme_pts > 0).mean():.0%} (median {f.stop_vs_extreme_pts.median()} pts)")
    print("  result by attempt number:", f.groupby("attempt")["profit"].agg(["size", "sum"]).to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
