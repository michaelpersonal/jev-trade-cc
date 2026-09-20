"""Macro regime from market-traded proxies.

Deliberately not FRED. CPI, payrolls and GDP are revised for years after
release, so using them honestly needs vintage (ALFRED) data -- and using the
current series would hand the backtest numbers nobody had at the time. Traded
prices are never revised, so a ratio of two ETFs is point-in-time by
construction.

  credit    HYG / IEF   high yield against duration-matched treasuries.
                        Falling = spreads widening = risk coming off, and
                        credit usually turns before equity does.
  rotation  XLY / XLU   consumer discretionary against utilities: what money
                        does when it wants offense rather than shelter.
  vol       ^VIX        against its own trailing year.

Each is scored risk-on/risk-off against its 50-day average, giving 0-3.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CACHE = RAW / "macro.parquet"
TICKERS = ["^VIX", "HYG", "IEF", "XLY", "XLU", "^TNX"]
START, END = "2020-09-01", "2026-09-19"


def prices(force: bool = False) -> pd.DataFrame:
    if CACHE.exists() and not force:
        d = pd.read_parquet(CACHE)
        d.index = pd.to_datetime(d.index)
        return d
    raw = yf.download(TICKERS, start=START, end=END, progress=False,
                      auto_adjust=False, group_by="column", threads=True)
    close = raw["Close"].copy()
    close.index.name = "Date"
    close.to_parquet(CACHE)
    return close


def features(force: bool = False) -> pd.DataFrame:
    c = prices(force)
    f = pd.DataFrame(index=c.index)

    credit = c["HYG"] / c["IEF"]
    f["credit"] = credit
    f["credit_on"] = credit > credit.rolling(50).mean()

    rot = c["XLY"] / c["XLU"]
    f["rotation"] = rot
    f["rotation_on"] = rot > rot.rolling(50).mean()

    vix = c["^VIX"]
    f["vix"] = vix
    # Calm relative to its own recent history, not an absolute level -- the
    # "normal" level of VIX drifts across regimes.
    f["vol_on"] = vix < vix.rolling(252, min_periods=120).quantile(0.70)

    f["score"] = (f["credit_on"].astype(int) + f["rotation_on"].astype(int)
                  + f["vol_on"].astype(int))
    return f


def apply_regime(base: pd.DataFrame, feat: pd.DataFrame, mode: int,
                 max_positions: int) -> pd.DataFrame:
    """Fold the macro score into the price regime.

    mode 0  price only, macro ignored
    mode 1  veto only: macro may downgrade a regime, never upgrade it
    mode 2  symmetric: a unanimous macro score may also upgrade YELLOW to GREEN

    Macro never creates a buy signal; it only decides how much of the book may
    be at risk when price and macro disagree.
    """
    out = base.copy()
    if mode == 0:
        return out
    s = feat["score"].reindex(out.index).ffill()
    reg = out["regime"].to_numpy(copy=True)
    for i, (r, sc) in enumerate(zip(reg, s.to_numpy())):
        if not np.isfinite(sc):
            continue
        if r == "GREEN" and sc < 2:
            reg[i] = "YELLOW"          # price says go, credit and vol disagree
        elif r == "YELLOW" and sc == 0:
            reg[i] = "RED"             # nothing is confirming; stand down
        elif mode == 2 and r == "YELLOW" and sc == 3:
            reg[i] = "GREEN"           # choppy price, but everything else is on
    out["regime"] = reg
    out["max_positions"] = np.where(reg == "GREEN", max_positions,
                                    np.where(reg == "YELLOW", max_positions // 2, 0))
    out["macro_score"] = s
    return out


if __name__ == "__main__":
    f = features(force=True)
    print(f.tail(3).round(2).to_string())
    w = f.loc["2022-01-03":"2026-09-18"]
    print("\nmacro score distribution:")
    print(w["score"].value_counts().sort_index().to_string())
    print("\nshare of days each leg is risk-on:")
    for k in ("credit_on", "rotation_on", "vol_on"):
        print(f"  {k:12s} {100*w[k].mean():.1f}%")
