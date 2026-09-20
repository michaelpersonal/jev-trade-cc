"""result.json + metrics -> web/data.js (one JS global the page reads)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import data as D
import metrics as M
import strategy as S
from backtest import CAPITAL

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    res = json.loads((ROOT / "data" / "result.json").read_text())
    idx = D.index_prices()
    daily, trades = res["daily"], res["trades"]
    dates = [d["date"] for d in daily]
    equity = [d["equity"] for d in daily]
    spx = M.benchmark(idx, dates, CAPITAL)

    strat_stats = M.summarize(equity, dates, "Jev")
    spx_stats = M.summarize(spx, dates, "S&P 500")
    tstats = M.trade_stats(trades)

    # Annual returns, side by side.
    eq = pd.Series(equity, index=pd.to_datetime(dates))
    bm = pd.Series(spx, index=pd.to_datetime(dates))
    years = sorted({d.year for d in eq.index})
    annual = []
    for y in years:
        a, b = eq[eq.index.year == y], bm[bm.index.year == y]
        prev_a = eq[eq.index < f"{y}-01-01"]
        prev_b = bm[bm.index < f"{y}-01-01"]
        a0 = prev_a.iloc[-1] if len(prev_a) else a.iloc[0]
        b0 = prev_b.iloc[-1] if len(prev_b) else b.iloc[0]
        annual.append(dict(year=y,
                           strat=round((a.iloc[-1] / a0 - 1) * 100, 1),
                           spx=round((b.iloc[-1] / b0 - 1) * 100, 1)))

    dd = M.drawdown(pd.Series(equity, index=pd.to_datetime(dates)))

    payload = dict(
        meta=dict(
            start=dates[0], end=dates[-1], capital=CAPITAL,
            rules=dict(stop=S.STOP_LOSS, target=S.PROFIT_TARGET,
                       max_positions=S.MAX_POSITIONS, rs_min=S.RS_MIN,
                       vol_surge=S.VOL_SURGE, hold_weeks=S.HOLD_WEEKS),
        ),
        dates=dates,
        equity=[round(x) for x in equity],
        spx=[round(x) for x in spx],
        dd=[round(float(x) * 100, 2) for x in dd],
        regime=[d["regime"] for d in daily],
        cash=[round(d["cash"]) for d in daily],
        positions=[d["positions"] for d in daily],
        trades=[d["trades"] for d in daily],
        stats=dict(strat=strat_stats, spx=spx_stats, trades=tstats),
        annual=annual,
        all_trades=trades,
    )
    out = ROOT / "web" / "data.js"
    out.parent.mkdir(exist_ok=True)
    out.write_text("window.JEV = " + json.dumps(payload, separators=(",", ":")) + ";")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")
    print(f"  Jev  {strat_stats['total_return']:+.1f}%  CAGR {strat_stats['cagr']:+.1f}%"
          f"  maxDD {strat_stats['max_dd']:.1f}%  ret/vol {strat_stats['return_vol']}")
    print(f"  SPX  {spx_stats['total_return']:+.1f}%  CAGR {spx_stats['cagr']:+.1f}%"
          f"  maxDD {spx_stats['max_dd']:.1f}%  ret/vol {spx_stats['return_vol']}")
    print(f"  trades {tstats.get('n_closed')} closed, win rate {tstats.get('win_rate')}%"
          f", profit factor {tstats.get('profit_factor')}")


if __name__ == "__main__":
    main()
