"""Phase 121b - study set: recent gap-fade setups at a low gap size, sorted into winners / losers / scratches.

Learning aid, not an edge. Minimum gap 0.2 x the 14-session range (about 3 setups a week per index),
fade toward yesterday's close, wide stop, exit 12:00, R before costs. WIN = at least +0.15R, LOSS =
at most -0.15R, SCRATCH in between. Also compares what winners and losers looked like on the full
3.5-year history (all setups at that size) with a permutation test, so the "lessons" are not guesses.

    python -m phase121b_learning_gallery            # last 5 weeks, both markets
    python -m phase121b_learning_gallery 8          # last 8 weeks
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase119_gap_charts as g

OUT = os.path.join(p1.ROOT, "exports", "gap_learning")
THR = 0.2


def label(r: float) -> str:
    return "WINS" if r >= 0.15 else "LOSSES" if r <= -0.15 else "SCRATCH"


def lessons(rows: pd.DataFrame) -> list:
    rng = np.random.default_rng(121)
    x = rows[(rows.entry == "0945") & (rows["size"] >= THR)].copy()
    w, l = x[x.r > 0], x[x.r <= 0]
    out = []
    for name, col in (("gap size (x normal range)", "size"), ("share of the gap closed toward the target by 09:45", "progress"), ("gap was UP (share)", "gap_up")):
        a, b = w[col].astype(float).to_numpy(), l[col].astype(float).to_numpy()
        diff = a.mean() - b.mean()
        pool = np.concatenate([a, b])
        perm = [rng.permutation(pool)[: len(a)].mean() - rng.permutation(pool)[: len(b)].mean() for _ in range(2000)]
        p = float((np.abs(perm) >= abs(diff)).mean())
        out.append({"feature": name, "winners": round(float(a.mean()), 3), "losers": round(float(b.mean()), 3), "p": round(p, 3), "p_bonf": round(min(1.0, p * 3), 3)})
    return [len(w), len(l)] + out


def main(argv=None) -> int:  # pragma: no cover
    weeks = int(argv[0]) if argv else 5
    lines = ["# Gap-fade study set (min gap 0.2x, wide stop, exit 12:00, R before costs)\n",
             "WINS = at least +0.15R, LOSSES = at most -0.15R, SCRATCH in between. Folders: WINS / LOSSES / SCRATCH.\n",
             "| Market | Day | Gap | Trade | Moved toward the target by 09:45 (negative = away) | Result | Ended by | Folder |", "|---|---|---|---|---|---|---|---|"]
    for sub in ("WINS", "LOSSES", "SCRATCH", "QUIZ"):
        d = os.path.join(OUT, sub)
        if os.path.isdir(d):
            for f in os.listdir(d):
                os.remove(os.path.join(d, f))
    counts = {"WINS": 0, "LOSSES": 0, "SCRATCH": 0}
    for m in ("NQ", "ES"):
        df = p1.load(m, "M1")
        df = df[df.index >= pd.Timestamp("2023-03-01")]
        sl = [s for s in g.setups(m, df, thr=THR) if s["day"] >= df.index.max().normalize() - pd.Timedelta(weeks=weeks)]
        for s in sl:
            sub = label(s["r"])
            counts[sub] += 1
            path = g.chart(s, df, os.path.join(OUT, sub))
            g.chart(s, df, os.path.join(OUT, "QUIZ"), blind=True)
            prog = (s["open"] - s["entry"]) / (s["open"] - s["pc"]) * 100
            lines.append(f"| {m} | {s['day']:%a %Y-%m-%d} | {'up' if s['gap'] > 0 else 'down'} {abs(s['gap']):,.1f} ({s['size']:.2f}x) | {'SHORT' if s['side'] < 0 else 'LONG'} toward {s['pc']:,.1f} | {prog:.0f}% | {s['r']:+.2f}R | {s['how']} | {sub}/{os.path.basename(path)} |")
    rows = pd.read_csv(os.path.join(p1.CACHE, "phase121", "phase121_rows.csv"), dtype={"entry": str})
    ls = lessons(rows)
    lines += ["", f"## What winners and losers looked like (all {ls[0] + ls[1]} NQ+ES setups at 0.2x since 2023: {ls[0]} winners, {ls[1]} losers)", "",
              "| Feature | Winners | Losers | p-value | after correction (3 tests) |", "|---|---|---|---|---|"]
    for r in ls[2:]:
        lines.append(f"| {r['feature']} | {r['winners']} | {r['losers']} | {r['p']} | {r['p_bonf']} |")
    os.makedirs(OUT, exist_ok=True)
    quiz = ["# Blind quiz", "",
            "For each file in the QUIZ folder: look at the chart (it stops at the 09:45 entry), decide YES or NO, and write one line why.",
            "Then open the same market and date in WINS / LOSSES / SCRATCH and see what happened. INDEX.md has every answer, so don't open it first.", "",
            "| Market | Day | Your call (yes/no) | Why | Result (fill in after) |", "|---|---|---|---|---|"]
    for ln in lines[6:]:
        if ln.startswith("| NQ") or ln.startswith("| ES"):
            c = [x.strip() for x in ln.strip("|").split("|")]
            quiz.append(f"| {c[0]} | {c[1]} |  |  |  |")
    open(os.path.join(OUT, "QUIZ.md"), "w", encoding="utf-8").write(chr(10).join(quiz) + chr(10))
    open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(counts)
    for r in ls[2:]:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
