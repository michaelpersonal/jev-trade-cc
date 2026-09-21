"""William O'Neil momentum rules, expressed as vectorised per-ticker indicators.

What is implemented, and which CAN SLIM letter it serves:

  L  Leader not laggard   -- RS Rating: IBD-style weighted relative strength,
                             percentile-ranked 1-99 against that day's universe.
  N  New high             -- price within reach of a 52-week high, breaking out
                             of a recognised base on a volume surge.
  S  Supply and demand    -- breakout volume >= 1.4x the 50-day average.
  M  Market direction     -- regime read off the S&P 500 (see market_regime).

  C / A / I are NOT implemented: earnings growth and institutional sponsorship
  need point-in-time fundamentals that yfinance cannot supply for delisted
  names. This is a technical reading of O'Neil, and the results should be read
  as such.

Every indicator on row `t` uses only data up to and including day `t`, and the
backtester acts on day `t+1`'s open. No lookahead anywhere.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --- tunables, all from O'Neil's own numbers ------------------------------
STOP_LOSS = 0.07          # "never let a loss exceed 7-8%"
PROFIT_TARGET = 0.25      # take most gains at 20-25%
FAST_MOVE = 0.20          # 20% within 3 weeks of breakout ...
FAST_MOVE_DAYS = 15       # ... (3 weeks of trading) ...
HOLD_WEEKS = 8            # ... means hold 8 weeks, it may be a big winner
MAX_POSITIONS = 8         # O'Neil favoured concentration over diversification
# Trailing exits, as an alternative to the fixed target. At most one is active;
# both None falls back to PROFIT_TARGET. The -7% hard stop always applies.
TRAIL_PCT = None          # give back this much of the peak close since entry
TRAIL_ATR = None          # chandelier: peak high minus this many ATR(20)

# Selection and regime overlays, both off by default.
GROUP_MIN_PCT = None      # require the stock's industry group in this top fraction
# How hard the market filter leans on the book:
#   0 none     ignore the market, always allow a full book
#   1 binary   RED blocks new buying, otherwise a full book
#   2 graded   RED blocks, YELLOW halves the book  (O'Neil-ish, the default)
# Jev in the loop. When on, Jev decides whether to take a candidate and
# whether a weakening position is a shakeout or a breakdown. The hard stop and
# the trailing stop stay in code and fire regardless.
# SHIPPED ON. Jev makes the buy and the hold/sell calls; code keeps the stops,
# the sizing and the fills. This is the point of the project.
JEV_ENTRY = True
JEV_EXIT = True
# Near-miss adjudication; see prereg_nearmiss.md. 0 off, 1 Jev, 2 mechanical
# count-matched to Jev, 3 mechanical unlimited.
# SHIPPED DEFAULT. 3 = admit near-misses mechanically, ranked by RS. This is
# the participation fix: the strict "first close above the pivot" screen
# produces only 22 buys a year against the 39 needed to keep 5 slots full, so
# the book sits ~43% in cash for want of candidates rather than by choice.
# Jev adjudication (mode 1) was tested against this and did not beat it.
# Stock selection. When on, the mechanical quality screen is bypassed: the
# candidate pool is every eligible name Jev assessed as a valid setup, and Jev
# chooses among them. Code keeps membership, tradability, sizing and stops.
JEV_SELECT = False
# 0 off · 1 Jev may override a 50-day sale · 2 Jev reviews every holding on a
# cadence and decides hold or sell on its own evidence
JEV_EXIT_MODE = 1
REVIEW_EVERY = 5          # sessions between routine reviews in mode 2

NEARMISS_MODE = 3
NEARMISS_QUOTA: dict = {}     # date -> n, used only by mode 2
NM_VOL_LO, NM_RS_LO = 1.15, 65
NM_DEPTH_LO, NM_DEPTH_HI = 0.05, 0.45

DEFER_MAX = 10            # sessions Jev may defer an exit; see deferral_contract.md

REGIME_MODE = 2
YELLOW_SLOTS = None       # slots allowed in YELLOW; None = MAX_POSITIONS // 2
MACRO_MODE = 0            # 0 off, 1 macro may veto, 2 macro may veto or confirm
RS_MIN = 80               # buy leaders: RS rating 80+
VOL_SURGE = 1.4           # breakout needs 40%+ above average volume
# BASE_MAX is the lookback for the pivot: the breakout must clear the highest
# high of the prior 13 weeks. BASE_MIN is a de-duplication window -- it
# suppresses a second signal within 5 weeks of the last one. Neither imposes a
# minimum age on the consolidation itself, and `base_len_wk` is frequently
# shorter than 5 weeks. Do not read these as "a 5-13 week base".
BASE_MIN, BASE_MAX = 25, 65      # de-dup window, pivot lookback (trading days)
BASE_DEPTH_MIN, BASE_DEPTH_MAX = 0.08, 0.35   # flat base .. deep cup
NEAR_HIGH = 0.85          # within 15% of the 52-week high
OFF_LOW = 1.25            # at least 25% above the 52-week low
MIN_PRICE = 10.0          # O'Neil avoided cheap stock
MIN_DOLLAR_VOL = 20e6     # tradeable: $20M/day average


def indicators(g: pd.DataFrame) -> pd.DataFrame:
    """Per-ticker indicator columns. `g` is one ticker, sorted by date."""
    g = g.copy()
    c, h, l, v = g["close"], g["high"], g["low"], g["volume"]

    g["ma50"] = c.rolling(50).mean()
    g["ma150"] = c.rolling(150).mean()
    g["ma200"] = c.rolling(200).mean()
    g["ma200_up"] = g["ma200"] > g["ma200"].shift(21)
    g["vol50"] = v.rolling(50).mean()
    g["dollar_vol"] = (c * v).rolling(50).mean()

    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    g["atr20"] = tr.rolling(20).mean()
    # A standing stop placed before the open cannot know today's true range.
    g["atr20_prev"] = g["atr20"].shift(1)

    g["hi52"] = h.rolling(252, min_periods=120).max()
    g["lo52"] = l.rolling(252, min_periods=120).min()

    # Trailing returns for the RS score (skip nothing -- momentum, not reversal)
    for n, lab in ((63, "r3"), (126, "r6"), (189, "r9"), (252, "r12")):
        g[lab] = c / c.shift(n) - 1.0

    # IBD weights the most recent quarter double.
    g["rs_score"] = (0.4 * g["r3"] + 0.2 * g["r6"]
                     + 0.2 * g["r9"] + 0.2 * g["r12"])

    # --- base and pivot ---------------------------------------------------
    # Resistance of the consolidation ending yesterday. Excluding today is what
    # makes a cross of it today a genuine breakout rather than a tautology.
    prior_high = h.shift(1).rolling(BASE_MAX).max()
    prior_low = l.shift(1).rolling(BASE_MAX).min()
    g["pivot"] = prior_high
    g["base_depth"] = 1.0 - prior_low / prior_high
    g["vol_ratio"] = v / g["vol50"]
    # How long the base actually ran: trading days since the pre-breakout high
    # was set. A five-week flat base and a thirteen-week cup are different
    # animals, and that difference is exactly what Jev is asked to judge.
    pos = h.shift(1).rolling(BASE_MAX).apply(
        lambda x: len(x) - 1 - int(np.argmax(x)), raw=True)
    g["base_len_wk"] = (pos + 1) / 5.0

    # Stage-2 trend template: the stock must already be in an advance.
    g["trend_ok"] = (
        (c > g["ma50"]) & (g["ma50"] > g["ma150"]) & (g["ma150"] > g["ma200"])
        & g["ma200_up"]
        & (c >= OFF_LOW * g["lo52"]) & (c >= NEAR_HIGH * g["hi52"])
    )

    # A breakout: first close above the base's resistance in BASE_MIN days,
    # out of a base of plausible depth, on real volume.
    crossed = (c > prior_high) & (c.shift(1) <= prior_high.shift(1))
    recent_cross = crossed.shift(1).astype(float).rolling(BASE_MIN).max()
    fresh = crossed & (recent_cross.fillna(0) == 0)
    g["breakout"] = (
        fresh
        & g["base_depth"].between(BASE_DEPTH_MIN, BASE_DEPTH_MAX)
        & (v > VOL_SURGE * g["vol50"])
        & g["trend_ok"]
        & (c >= MIN_PRICE)
        & (g["dollar_vol"] >= MIN_DOLLAR_VOL)
    )
    return g


def build_signals(panel: pd.DataFrame, membership: dict | None = None) -> pd.DataFrame:
    """Panel -> panel + indicators + cross-sectional RS rating (1-99).

    `membership` maps snapshot date -> set of tickers in the index then. When
    given, RS is ranked only against names that were actually in the index on
    that date. Without it the reference population is the union of every name
    that was EVER a member, which leaks future membership into a rank that is
    supposed to describe the past.
    """
    # Iterate rather than .apply(): pandas 3 drops the grouping column inside
    # apply, and we need `ticker` to survive.
    parts = [indicators(g) for _, g in
             panel.sort_values(["ticker", "date"]).groupby("ticker", sort=True)]
    out = pd.concat(parts, ignore_index=True)
    # RS rating is a rank against every other stock in that day's investable
    # population, which is why it can only be computed once the whole panel is
    # in hand -- and why the population has to be the historical one.
    if membership:
        snaps = sorted(membership)
        eligible = pd.Series(False, index=out.index)
        for i, snap in enumerate(snaps):
            lo = pd.Timestamp.min if i == 0 else snap
            hi = snaps[i + 1] if i + 1 < len(snaps) else pd.Timestamp.max
            m = (out["date"] >= lo) & (out["date"] < hi)
            eligible |= m & out["ticker"].isin(membership[snap])
        scored = out["rs_score"].where(eligible)
    else:
        scored = out["rs_score"]
    out["rs_rating"] = (
        scored.groupby(out["date"]).rank(pct=True) * 98 + 1
    ).round()
    out["buyable"] = out["breakout"] & (out["rs_rating"] >= RS_MIN)

    # Near-miss: every structural requirement holds and exactly one relaxable
    # test fails, inside its band. Frozen in prereg_nearmiss.md.
    core = (out["trend_ok"].fillna(False) & (out["close"] >= MIN_PRICE)
            & (out["dollar_vol"] >= MIN_DOLLAR_VOL))
    fresh = out["close"] > out["pivot"]
    t_vol = out["vol_ratio"] >= VOL_SURGE
    t_rs = out["rs_rating"] >= RS_MIN
    t_dep = out["base_depth"].between(BASE_DEPTH_MIN, BASE_DEPTH_MAX)
    b_vol = out["vol_ratio"].between(NM_VOL_LO, VOL_SURGE, inclusive="left")
    b_rs = out["rs_rating"].between(NM_RS_LO, RS_MIN, inclusive="left")
    b_dep = (out["base_depth"].between(NM_DEPTH_LO, BASE_DEPTH_MIN, inclusive="left")
             | out["base_depth"].between(BASE_DEPTH_MAX, NM_DEPTH_HI, inclusive="right"))
    fails = ((~t_vol).astype(int) + (~t_rs).astype(int) + (~t_dep).astype(int))
    out["nearmiss"] = (fresh & core & (t_vol | b_vol) & (t_rs | b_rs)
                       & (t_dep | b_dep) & (fails == 1)
                       & ~out["buyable"].fillna(False))
    return out


def market_regime(idx: pd.DataFrame) -> pd.DataFrame:
    """O'Neil's M: three in four stocks follow the market, so read it first.

    GREEN  uptrend confirmed      -> full exposure
    YELLOW above the 200 but sick -> half exposure
    RED    below the 200          -> no new buys
    """
    d = pd.DataFrame(index=idx.index)
    c = idx["Close"]
    d["close"] = c
    d["ma50"] = c.rolling(50).mean()
    d["ma200"] = c.rolling(200).mean()
    green = (c > d["ma50"]) & (d["ma50"] > d["ma200"])
    yellow = (~green) & (c > d["ma200"])
    d["regime"] = np.where(green, "GREEN", np.where(yellow, "YELLOW", "RED"))
    if REGIME_MODE == 0:
        d["regime"] = "GREEN"
        d["max_positions"] = MAX_POSITIONS
    elif REGIME_MODE == 1:
        d["max_positions"] = np.where(d["regime"] == "RED", 0, MAX_POSITIONS)
    else:
        ys = MAX_POSITIONS // 2 if YELLOW_SLOTS is None else YELLOW_SLOTS
        d["max_positions"] = np.where(green, MAX_POSITIONS,
                                      np.where(yellow, ys, 0))
    return d
