"""Regression tests for the decision-time boundary.

The rule under test: information that only exists after an order has filled
must not be able to change whether that fill happened. These would have caught
the defect Codex found, where the position limit gating an open fill was read
from the same day's close.

Run: ../.venv/bin/python test_timing.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import backtest as B
import strategy as S


def _panel(n=420, seed=0):
    """One ticker: a long advance, then a cup-shaped base, then a breakout.

    The base has to be deep enough to clear BASE_DEPTH_MIN and shallow enough
    to stay under BASE_DEPTH_MAX, or no signal fires and the timing test is
    vacuous.
    """
    dates = pd.bdate_range("2021-01-04", periods=n)
    px = np.linspace(20.0, 140.0, n)            # steep advance, so the 50-day
    rim = px[-41]                               # stays above the 150-day
    cup = np.concatenate([                      # through the consolidation
        np.linspace(rim, rim * 0.88, 20),       # 12% deep left side
        np.linspace(rim * 0.88, rim * 0.99, 19),  # recovery to the rim
    ])
    px[-41:-2] = cup
    px[-2] = rim * 1.05                         # breakout through the rim
    px[-1] = px[-2] * 1.01
    vol = np.full(n, 3e6)
    vol[-2] = 9e6
    return pd.DataFrame(dict(
        date=dates, ticker="TEST", open=px * 0.995, high=px * 1.005,
        low=px * 0.99, close=px, volume=vol))


def _index(dates, last_close):
    """SPX rising all year, with the final close settable."""
    c = np.linspace(3000, 4200, len(dates))
    c[-1] = last_close
    return pd.DataFrame(dict(Close=c, Open=c, High=c, Low=c), index=dates)


def test_close_cannot_change_an_open_fill() -> bool:
    """Changing the LAST close must not change fills that happened at its open."""
    pan = _panel()
    sig = S.build_signals(pan)
    sig["buyable"] = sig["breakout"].fillna(False)
    memb = {pd.Timestamp("2021-01-01"): {"TEST"}}
    bd = B.index_by_date(sig)
    dates = pd.DatetimeIndex(sorted(sig["date"].unique()))
    start = str(dates[300].date())
    end = str(dates[-1].date())

    counts = []
    for last_close in (4200.0, 1.0):        # 1.0 forces the final regime to RED
        idx = _index(dates, last_close)
        r = B.run(sig, idx, memb, start=start, end=end, capital=100_000.0,
                  by_date=bd)
        fills = [t for t in r["trades"]
                 if t["side"] == "BUY" and t["date"] == end]
        counts.append(len(fills))

    # A test that never fills would pass trivially, so require a real fill.
    if counts[0] == 0:
        print("  VACUOUS: no fill occurred, the test proves nothing  ->  FAIL")
        return False
    ok = counts[0] == counts[1]
    print(f"  buys at the final open: normal close={counts[0]}, "
          f"crashed close={counts[1]}  ->  {'PASS' if ok else 'FAIL'}")
    return ok


def test_atr_stop_excludes_todays_range() -> bool:
    """The chandelier stop must be built from ATR through yesterday."""
    pan = _panel()
    sig = S.build_signals(pan)
    has_prev = "atr20_prev" in sig.columns
    if not has_prev:
        print("  atr20_prev missing  ->  FAIL")
        return False
    a = sig.dropna(subset=["atr20", "atr20_prev"])
    shifted = np.allclose(a["atr20_prev"].to_numpy()[1:],
                          a["atr20"].to_numpy()[:-1])
    src = (__import__("pathlib").Path(__file__).parent / "backtest.py").read_text()
    uses_prev = 'px(tkr, "atr20_prev")' in src and 'px(tkr, "atr20")' not in src
    ok = shifted and uses_prev
    print(f"  atr20_prev is atr20 lagged one bar: {shifted}; "
          f"backtest uses the lagged series: {uses_prev}  ->  "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    print("decision-time boundary:")
    results = [test_close_cannot_change_an_open_fill(),
               test_atr_stop_excludes_todays_range()]
    print("ALL PASS" if all(results) else "FAILURES PRESENT")
    sys.exit(0 if all(results) else 1)
