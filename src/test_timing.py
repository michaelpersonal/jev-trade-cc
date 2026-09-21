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
    S.JEV_ENTRY = S.JEV_EXIT = False      # this test is about the rules only
    S.NEARMISS_MODE = 0
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





# ---------------------------------------------------------------------------
# Integration guards for the Jev hooks (codex-integration-review.md)
# ---------------------------------------------------------------------------
def test_uninitialised_provider_is_an_error() -> bool:
    """JEV_ENTRY without loaded history must raise, not silently go to cash."""
    import backtest
    backtest._PANEL, backtest._WEEKLY = {}, {}
    pan = _panel()
    sig = S.build_signals(pan)
    sig["buyable"] = sig["breakout"].fillna(False)
    memb = {pd.Timestamp("2021-01-01"): {"TEST"}}
    dates = pd.DatetimeIndex(sorted(sig["date"].unique()))
    S.JEV_ENTRY, S.JEV_EXIT, S.NEARMISS_MODE = True, False, 0
    try:
        B.run(sig, _index(dates, 4200.0), memb, start=str(dates[300].date()),
              end=str(dates[-1].date()), capital=100_000.0)
        ok = False
    except RuntimeError:
        ok = True
    finally:
        S.JEV_ENTRY = False
    print(f"  uninitialised evidence provider raises  ->  {'PASS' if ok else 'FAIL'}")
    return ok


def test_weekly_cache_invalidates() -> bool:  # noqa: D401
    """A reload must not serve bars built from the previous panel, and the
    lookback must be part of the cache identity."""
    import backtest
    pan = _panel()
    backtest.load_panel(pan)
    a16 = backtest.weekly_bars("TEST", pan["date"].iloc[-1], weeks=16)
    a8 = backtest.weekly_bars("TEST", pan["date"].iloc[-1], weeks=8)
    len_ok = (a16 is not None and a8 is not None
              and len(a16) == 16 and len(a8) == 8)
    bumped = pan.copy()
    bumped[["open", "high", "low", "close"]] *= 2.0
    backtest.load_panel(bumped)
    b16 = backtest.weekly_bars("TEST", pan["date"].iloc[-1], weeks=16)
    fresh_ok = b16 is not None and abs(
        float(b16["close"].iloc[-1]) / float(a16["close"].iloc[-1]) - 2.0) < 1e-6
    ok = len_ok and fresh_ok
    print(f"  weekly cache keys on lookback ({len_ok}) and clears on reload "
          f"({fresh_ok})  ->  {'PASS' if ok else 'FAIL'}")
    return ok


def _shakeout_panel(n=560):
    """Breakout, then a long shallow drift that dips under the rising 50-day
    while staying inside the 7% stop and the 15% trailing stop -- the exact
    state a deferral episode is meant to cover."""
    dates = pd.bdate_range("2021-01-04", periods=n)
    px = np.linspace(20.0, 140.0, n)
    rim = px[-141]
    cup = np.concatenate([np.linspace(rim, rim * 0.88, 20),
                          np.linspace(rim * 0.88, rim * 0.99, 19)])
    px[-141:-102] = cup
    px[-102] = rim * 1.05                      # breakout
    # A long shallow drift. It runs well past DEFER_MAX so the episode can
    # reach expiry, and stays inside 7% of entry so no stop pre-empts it.
    px[-101:] = np.linspace(rim * 1.05, rim * 0.99, 101)
    vol = np.full(n, 3e6)
    vol[-102] = 9e6
    return pd.DataFrame(dict(
        date=dates, ticker="TEST", open=px * 0.995, high=px * 1.005,
        low=px * 0.99, close=px, volume=vol))


def test_deferral_is_bounded() -> bool:
    """A model that always says hold must not defer an exit indefinitely."""
    import backtest
    import jev
    S.JEV_ENTRY, S.NEARMISS_MODE = False, 0   # isolate the exit path
    pan = _shakeout_panel()
    backtest.load_panel(pan)
    sig = S.build_signals(pan)
    sig["buyable"] = sig["breakout"].fillna(False)
    memb = {pd.Timestamp("2021-01-01"): {"TEST"}}
    dates = pd.DatetimeIndex(sorted(sig["date"].unique()))
    real = jev.decide_exit
    jev.decide_exit = lambda *a, **k: {"action": {"choice": "override"}}
    # This guard tests the MODE 1 deferral contract specifically, so it pins
    # the mode rather than inheriting whichever one ships. It relied on the
    # default being 1 and went vacuous the moment the shipped default moved
    # to 2 -- the anti-vacuity check caught it, which is what it is for.
    S.JEV_EXIT, S.JEV_EXIT_MODE = True, 1
    try:
        r = B.run(sig, _index(dates, 4200.0), memb,
                  start=str(dates[300].date()), end=str(dates[-1].date()),
                  capital=100_000.0)
        holds = r["jev_holds"]
        expired = [t for t in r["trades"]
                   if t.get("reason") == "Jev: deferral expired"]
    finally:
        jev.decide_exit = real
        S.JEV_EXIT, S.JEV_EXIT_MODE = False, S.JEV_EXIT_MODE
    if holds == 0:
        print("  VACUOUS: no deferral episode opened, the test proves nothing"
              "  ->  FAIL")
        return False
    ok = holds <= S.DEFER_MAX and len(expired) == 1
    print(f"  always-hold model deferred {holds} times (cap {S.DEFER_MAX}) and "
          f"the exit was forced at expiry ({len(expired)})  ->  "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def test_bad_response_is_not_a_decision() -> bool:
    """An unexpected label must be rejected, not silently read as hold."""
    import jev
    try:
        jev.choice_of({"action": {"choice": "maybe"}}, "action", {"hold", "sell"})
        ok = False
    except jev.JevUnavailable:
        ok = True
    try:
        jev.score_of({"conviction": {}}, "conviction")
        ok = ok and False
    except jev.JevUnavailable:
        pass
    print(f"  unexpected label and missing score both rejected  ->  "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    print("decision-time boundary:")
    results = [test_close_cannot_change_an_open_fill(),
               test_atr_stop_excludes_todays_range()]
    print("jev integration guards:")
    results += [test_uninitialised_provider_is_an_error(),
                test_weekly_cache_invalidates(),
                test_deferral_is_bounded(),
                test_bad_response_is_not_a_decision()]
    print("ALL PASS" if all(results) else "FAILURES PRESENT")
    sys.exit(0 if all(results) else 1)
