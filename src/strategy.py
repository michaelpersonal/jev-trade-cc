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
REGIME_MODE = 2
YELLOW_SLOTS = None       # slots allowed in YELLOW; None = MAX_POSITIONS // 2
MACRO_MODE = 0            # 0 off, 1 macro may veto, 2 macro may veto or confirm
RS_MIN = 80               # buy leaders: RS rating 80+
VOL_SURGE = 1.4           # breakout needs 40%+ above average volume
BASE_MIN, BASE_MAX = 25, 65      # base length in trading days (5-13 weeks)
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


def build_signals(panel: pd.DataFrame) -> pd.DataFrame:
    """Panel -> panel + indicators + cross-sectional RS rating (1-99)."""
    # Iterate rather than .apply(): pandas 3 drops the grouping column inside
    # apply, and we need `ticker` to survive.
    parts = [indicators(g) for _, g in
             panel.sort_values(["ticker", "date"]).groupby("ticker", sort=True)]
    out = pd.concat(parts, ignore_index=True)
    # RS rating is a rank *against every other stock that day*, which is why it
    # can only be computed once the whole panel is in hand.
    out["rs_rating"] = (
        out.groupby("date")["rs_score"].rank(pct=True) * 98 + 1
    ).round()
    out["buyable"] = out["breakout"] & (out["rs_rating"] >= RS_MIN)
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
