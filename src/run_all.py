"""Produce every number the web page shows.

Primary run holds five positions (O'Neil's own guidance for a $20k-$200k
account) and exits on a 15% trailing stop rather than his fixed 20-25% target.
The target capped every winner that mattered -- NVDA at +25% three weeks before
it tripled -- so the trailing stop replaces it. The second curve keeps the
target, as written, so the contrast stays visible.

The -15% figure is not tuned: anything from 15% to 25% is the same decision,
and the trailing stop's real contribution is simply that it stops capping
winners. See the split-half columns in the exit-rule table.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import backtest as B
import data as D
import metrics as M
import strategy as S
import universe as U

ROOT = Path(__file__).resolve().parent.parent


def config(slots: int, target: float | None):
    S.MAX_POSITIONS, S.PROFIT_TARGET = slots, target


def main() -> None:
    # signals_grouped carries the group ranks AND the near-miss column; it is
    # the single source of truth for every runner.
    sig = pd.read_parquet(ROOT / "data" / "raw" / "signals_grouped.parquet")
    idx = D.index_prices()
    B.load_panel(pd.read_parquet(ROOT / "data" / "raw" / "panel.parquet"))
    memb = U.membership()

    def cfg(target=None, tpct=None, tatr=None, slots=5, jev=True):
        S.MAX_POSITIONS, S.PROFIT_TARGET = slots, target
        S.TRAIL_PCT, S.TRAIL_ATR = tpct, tatr
        # The exit-rule grid and the slot sweep compare RULES. Running them
        # with Jev in the loop would conflate the model with the rule under
        # test, so they run rules-only and are labelled as such.
        S.JEV_ENTRY = S.JEV_EXIT = jev

    cfg(tpct=0.15)
    primary = B.run(sig, idx, memb)
    cfg(target=0.25)                # O'Neil as written, kept for contrast
    variant = B.run(sig, idx, memb)
    cfg(tpct=0.15)

    daily, trades = primary["daily"], primary["trades"]
    dates = [d["date"] for d in daily]
    equity = primary["equity"]
    aswritten = variant["equity"]
    spx = M.benchmark(idx, dates, B.CAPITAL)

    # --- exit rules, each scored on the whole run and on each half ---------
    # Splitting the sample is the only cheap defence against reading noise as
    # edge: a rule that is genuinely better should win in both halves.
    HALVES = (("2022-01-03", "2024-03-28"), ("2024-04-01", "2026-09-18"))
    RULES = [("Take 20-25% (O'Neil as written)", dict(target=0.25)),
             ("No exit target at all", dict())]
    RULES += [(f"Trailing stop -{t:.0%}", dict(tpct=t))
              for t in (0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25)]
    RULES += [(f"Chandelier {a:g}x ATR", dict(tatr=a)) for a in (2.5, 3.0, 4.0)]

    def span(kw, start, end):
        cfg(**kw, jev=False)
        B.START, B.END = start, end
        r = B.run(sig, idx, memb)
        st = M.summarize(r["equity"], r["dates"], "x")
        bm = M.summarize(M.benchmark(idx, r["dates"], B.CAPITAL), r["dates"], "b")
        return st, bm, r

    grid = []
    for label, kw in RULES:
        full, bm_full, r = span(kw, "2022-01-03", "2026-09-18")
        h1, bm1, _ = span(kw, *HALVES[0])
        h2, bm2, _ = span(kw, *HALVES[1])
        ts = M.trade_stats(r["trades"])
        grid.append(dict(rule=label, total=full["total_return"], cagr=full["cagr"],
                         max_dd=full["max_dd"], return_vol=full["return_vol"],
                         h1=h1["total_return"], h2=h2["total_return"],
                         trades=ts["n_closed"], win=ts["win_rate"]))
    B.START, B.END = "2022-01-03", "2026-09-18"
    halves = dict(h1=dict(label="2022-01 to 2024-03", spx=round(bm1["total_return"], 1)),
                  h2=dict(label="2024-04 to 2026-09", spx=round(bm2["total_return"], 1)),
                  full=round(bm_full["total_return"], 1))

    # position count, held separately -- it turned out not to matter
    slots_grid = []
    for n in (3, 4, 5, 6, 8):
        cfg(tpct=0.15, slots=n, jev=False)
        r = B.run(sig, idx, memb)
        st = M.summarize(r["equity"], r["dates"], "x")
        slots_grid.append(dict(slots=n, total=st["total_return"], max_dd=st["max_dd"]))
    cfg(tpct=0.15)

    eq = pd.Series(equity, index=pd.to_datetime(dates))
    bm = pd.Series(spx, index=pd.to_datetime(dates))
    annual = []
    for y in sorted({d.year for d in eq.index}):
        a, b = eq[eq.index.year == y], bm[bm.index.year == y]
        pa, pb = eq[eq.index < f"{y}-01-01"], bm[bm.index < f"{y}-01-01"]
        a0 = pa.iloc[-1] if len(pa) else a.iloc[0]
        b0 = pb.iloc[-1] if len(pb) else b.iloc[0]
        annual.append(dict(year=y, strat=round((a.iloc[-1] / a0 - 1) * 100, 1),
                           spx=round((b.iloc[-1] / b0 - 1) * 100, 1)))

    # --- data coverage, stated plainly on the page ------------------------
    uni = U.build()
    panel = D.panel([])
    ever, have = set(uni["ticker"]), set(panel["ticker"].unique())
    missing = sorted(ever - have)
    n_sig = int(sig[(sig["date"] >= "2022-01-03") & sig["buyable"].fillna(False)].shape[0])

    stats = dict(strat=M.summarize(equity, dates, "Jev deciding"),
                 spx=M.summarize(spx, dates, "S&P 500"),
                 aswritten=M.summarize(aswritten, dates, "Rules only (20-25% target)"),
                 trades=M.trade_stats(trades))

    payload = dict(
        meta=dict(
            start=dates[0], end=dates[-1], capital=B.CAPITAL,
            rules=dict(stop=S.STOP_LOSS, target=S.PROFIT_TARGET,
                       trail=S.TRAIL_PCT,
                       max_positions=S.MAX_POSITIONS, rs_min=S.RS_MIN,
                       vol_surge=S.VOL_SURGE, hold_weeks=S.HOLD_WEEKS),
            universe=dict(ever=len(ever), have=len(have), missing=len(missing),
                          missing_sample=missing[:12]),
            signals=n_sig,
            coverage=(
                f"The point-in-time universe names {len(ever)} distinct tickers across "
                f"{uni['snapshot_date'].nunique()} quarterly snapshots. Price history was "
                f"available for {len(have)}; {len(missing)} left no usable history on "
                f"Yahoo Finance after their delisting (ATVI, CERN, FRC, SIVB and similar). "
                f"Those {len(missing)} are the residual survivorship bias in this run — "
                f"small, but it leans the result slightly favourable, since a name that "
                f"vanishes is more often a failure than a success."),
        ),
        dates=dates,
        equity=[round(x) for x in equity],
        aswritten=[round(x) for x in aswritten],
        spx=[round(x) for x in spx],
        dd=[round(float(x) * 100, 2) for x in M.drawdown(eq)],
        regime=[d["regime"] for d in daily],
        cash=[round(d["cash"]) for d in daily],
        positions=[d["positions"] for d in daily],
        trades=[d["trades"] for d in daily],
        stats=stats, annual=annual, grid=grid, halves=halves, slots=slots_grid,
    )
    (ROOT / "data" / "result.json").write_text(
        json.dumps(primary, default=str))   # primary config, for inspection
    exp = ROOT / "data" / "experiments.json"
    payload["experiments"] = json.loads(exp.read_text()) if exp.exists() else None
    out = ROOT / "web" / "data.js"
    out.write_text("window.JEV = " + json.dumps(payload, separators=(",", ":")) + ";")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")
    for k in ("strat", "aswritten", "spx"):
        s = stats[k]
        print(f"  {s['label']:18s} {s['total_return']:+7.1f}%  CAGR {s['cagr']:+6.2f}%  "
              f"maxDD {s['max_dd']:6.1f}%  ret/vol {s['return_vol']}")
    t = stats["trades"]
    print(f"  {t['n_closed']} closed trades, win rate {t['win_rate']}%, "
          f"profit factor {t['profit_factor']}, {n_sig} buy signals available")
    print(f"  universe {len(ever)} ever / {len(have)} with data / {len(missing)} missing")


if __name__ == "__main__":
    main()
