"""Walk-forward evaluation.

Fit on a trailing window, trade the next six months with whatever that window
chose, step forward, repeat. The stitched test segments are the only genuinely
out-of-sample record: no parameter was ever chosen using the data it is scored
on.

The comparison that matters is not the walk-forward return on its own. It is
the walk-forward return against simply fixing one sensible setting and never
touching it. If adaptive selection cannot beat a constant, the parameters were
noise and the honest move is to stop fitting them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import backtest as B
import data as D
import macro as MAC
import metrics as M
import strategy as S
import universe as U

ROOT = Path(__file__).resolve().parent.parent
TRAIN_M, TEST_M, STEP_M = 18, 6, 6
SPAN = ("2022-01-03", "2026-09-18")

GRID = [dict(trail=t, macro=m, group=g)
        for t in (0.10, 0.15, 0.20, 0.25)
        for m in (0, 1, 2)
        for g in (None, 0.50, 0.75)]

FIXED = dict(trail=0.15, macro=0, group=None)   # the constant we must beat


def apply(p: dict) -> None:
    S.MAX_POSITIONS, S.PROFIT_TARGET, S.TRAIL_ATR = 5, None, None
    S.TRAIL_PCT, S.MACRO_MODE, S.GROUP_MIN_PCT = p["trail"], p["macro"], p["group"]


def label(p: dict) -> str:
    g = "off" if p["group"] is None else f"top{int((1-p['group'])*100)}%"
    return f"trail {p['trail']:.0%} / macro {p['macro']} / group {g}"


def folds() -> list[tuple[str, str, str, str]]:
    out, t0 = [], pd.Timestamp(SPAN[0])
    last = pd.Timestamp(SPAN[1])
    while True:
        tr_end = t0 + pd.DateOffset(months=TRAIN_M)
        te_end = min(tr_end + pd.DateOffset(months=TEST_M), last)
        if tr_end >= last:
            break
        # test starts the day after training ends, so no bar is in both
        out.append((str(t0.date()), str(tr_end.date()),
                    str((tr_end + pd.Timedelta(days=1)).date()), str(te_end.date())))
        if te_end >= last:
            break
        t0 += pd.DateOffset(months=STEP_M)
    return out


def main() -> None:
    gp = ROOT / "data" / "raw" / "signals_grouped.parquet"
    sig = pd.read_parquet(gp if gp.exists()
                          else ROOT / "data" / "raw" / "signals.parquet")
    idx, memb, feat = D.index_prices(), U.membership(), MAC.features()
    by_date = B.index_by_date(sig)
    kw = dict(by_date=by_date, feat=feat)

    rows, wf_equity, fx_equity = [], B.CAPITAL, B.CAPITAL
    curve, dates_all = [], []
    for tr0, tr1, te0, te1 in folds():
        best, best_score = None, -9e9
        for p in GRID:
            apply(p)
            r = B.run(sig, idx, memb, start=tr0, end=tr1, capital=B.CAPITAL, **kw)
            score = r["final"]
            if score > best_score:
                best, best_score = p, score

        apply(best)
        te = B.run(sig, idx, memb, start=te0, end=te1, capital=wf_equity, **kw)
        wf_ret = te["final"] / wf_equity - 1
        wf_equity = te["final"]

        apply(FIXED)
        fx = B.run(sig, idx, memb, start=te0, end=te1, capital=fx_equity, **kw)
        fx_ret = fx["final"] / fx_equity - 1
        fx_equity = fx["final"]

        c = idx["Close"]
        seg = c.loc[te["dates"][0]:te["dates"][-1]]
        sp_ret = float(seg.iloc[-1] / seg.iloc[0] - 1)

        rows.append(dict(train=f"{tr0} .. {tr1}", test=f"{te0} .. {te1}",
                         chosen=label(best), train_return=round((best_score/B.CAPITAL-1)*100, 1),
                         wf=round(wf_ret*100, 1), fixed=round(fx_ret*100, 1),
                         spx=round(sp_ret*100, 1), trades=len(te["trades"])))
        curve += [round(x, 2) for x in te["equity"]]
        dates_all += [str(d) for d in te["dates"]]
        print(f"{rows[-1]['test']}  chose {label(best):38s} "
              f"wf {wf_ret*100:+6.1f}%  fixed {fx_ret*100:+6.1f}%  spx {sp_ret*100:+6.1f}%")

    print("\n" + "="*78)
    n = len(rows)
    print(f"{n} out-of-sample folds, {dates_all[0]} -> {dates_all[-1]}")
    print(f"  walk-forward   ${wf_equity:>10,.0f}  ({wf_equity/B.CAPITAL-1:+.1%})")
    print(f"  fixed params   ${fx_equity:>10,.0f}  ({fx_equity/B.CAPITAL-1:+.1%})")
    c = idx["Close"]
    sp0, sp1 = c.loc[dates_all[0]], c.loc[dates_all[-1]]
    print(f"  S&P 500        ${B.CAPITAL*sp1/sp0:>10,.0f}  ({sp1/sp0-1:+.1%})")
    wins = sum(1 for r in rows if r["wf"] > r["fixed"])
    print(f"\n  walk-forward beat the constant in {wins}/{n} folds")
    print(f"  distinct parameter sets chosen: "
          f"{len({r['chosen'] for r in rows})} of {n} folds")
    for r in rows:
        print(f"    {r['test']}  {r['chosen']}")

    (ROOT / "data" / "walkforward.json").write_text(json.dumps(
        dict(folds=rows, equity=curve, dates=dates_all,
             final_wf=wf_equity, final_fixed=fx_equity,
             spx=float(B.CAPITAL*sp1/sp0)), default=str))


if __name__ == "__main__":
    main()
