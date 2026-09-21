"""Strategy-comprehension exam: does Jev apply O'Neil's base criteria?

Separate from profitability. A correct pattern reading can still lose money and
a profitable trade can violate the method; this file scores only the first.

Labels are not adjudicated by anyone. Each case is GENERATED from a chosen
shape, so the expected answer follows from how the bars were built. Cases come
in pairs that differ in exactly one dimension and are otherwise identical, so a
score difference can only come from that dimension. A model that ignores volume
entirely, for example, cannot pass the volume pair by luck.

Dimensions tested, each from O'Neil's published criteria:
  volume     supply drying up through the base, expanding on the breakout
  extension  buying at the pivot rather than far above it
  tightness  weekly ranges narrowing through the second half of the base
  advance    a real prior uptrend the base is resting from
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEEKS = 16


def _bars(closes, vols, width):
    """Weekly OHLC from a close path, a volume path and a per-week range width."""
    rows = []
    for i, (c, v, w) in enumerate(zip(closes, vols, width)):
        o = closes[i - 1] if i else c * 0.995
        hi = max(o, c) * (1 + w)
        lo = min(o, c) * (1 - w)
        rows.append(dict(open=o, high=hi, low=lo, close=c, vol_rel=v))
    return pd.DataFrame(rows)


def case(dim: str, arm: str, seed: int) -> tuple[pd.DataFrame, dict]:
    """One exam case. `arm` is 'good' (matches the method) or 'bad'.

    Two invariants the earlier version did not hold, and which made its
    results uninterpretable:

    * **The paired arms differ only in the named dimension.** Noise is drawn
      once per seed and shared, so the volume pair really is the same price
      path with different volume. Previously each arm re-drew, so all sixteen
      bars differed and a "volume" pair was two unrelated charts.
    * **The pivot is derived, not asserted.** It is the highest high of the
      bars actually generated before the breakout week, and the final close is
      then placed a chosen distance above it. Previously pivot was hardcoded
      to 100 while the generated highs ran past 102, so the "good" extension
      cases did not clear their own stated breakout level at all.
    """
    rng = np.random.default_rng(seed)
    n = WEEKS
    noise = rng.normal(0, .004, n - 1)        # shared by both arms
    wide = rng.normal(0, .035, 9)             # shared; used only by tightness

    adv = np.linspace(72, 100, 6)
    rest = np.concatenate([np.linspace(100, 88, 4), np.linspace(88, 99, 5)])
    closes = np.concatenate([adv, rest])[:n - 1] * (1 + noise)
    vols = np.concatenate([np.full(6, 1.0), np.full(9, .62)])[:n - 1]
    width = np.concatenate([np.full(6, .012),
                            np.linspace(.020, .008, 9)])[:n - 1]

    break_vol, extension = 1.9, 0.015         # good-arm defaults

    if dim == "volume" and arm == "bad":
        vols = np.concatenate([np.full(6, 1.0), np.full(9, 1.45)])[:n - 1]
        break_vol = 0.85                      # quiet break, heavy base
    elif dim == "extension" and arm == "bad":
        extension = 0.18                      # far beyond the buy zone
    elif dim == "tightness" and arm == "bad":
        width = np.concatenate([np.full(6, .012), np.full(9, .042)])[:n - 1]
        closes = closes.copy()
        closes[6:15] = closes[6:15] * (1 + wide[:len(closes[6:15])])
    elif dim == "advance" and arm == "bad":
        closes = np.concatenate([np.linspace(132, 100, 6),
                                 rest])[:n - 1] * (1 + noise)

    prior = _bars(closes, vols, width)
    # The buy point is the highest high of the base, measured on the bars that
    # exist. Everything downstream is stated relative to this number.
    pivot = float(prior["high"].max())
    final_close = pivot * (1 + extension)
    bars = pd.concat([prior, _bars_one(prior["close"].iloc[-1], final_close,
                                       break_vol, .014)], ignore_index=True)

    up = not (dim == "advance" and arm == "bad")
    c = final_close
    base = prior.iloc[6:]          # the consolidation, after the advance
    row = dict(pivot=pivot, close=c, rs_rating=88.0,
               base_depth=float(1 - base["low"].min() / pivot),
               base_len_wk=float(len(base)),
               hi52=float(bars["high"].max()), lo52=float(bars["low"].min()) * .72,
               dollar_vol=140e6, group_pct=0.86, regime="GREEN",
               ma50=c * (0.95 if up else 0.99),
               ma150=c * (0.88 if up else 1.02),
               ma200=c * (0.82 if up else 1.06), ma200_up=up)
    return bars, row


def _bars_one(prev_close, close, vol_rel, w):
    """The breakout week, opening from the prior close."""
    o = float(prev_close)
    return pd.DataFrame([dict(open=o, high=max(o, close) * (1 + w),
                              low=min(o, close) * (1 - w), close=float(close),
                              vol_rel=float(vol_rel))])


DIMS = ("volume", "extension", "tightness", "advance")


def build(n_per_dim: int = 12) -> list[dict]:
    out = []
    for d in DIMS:
        for k in range(n_per_dim):
            for arm in ("good", "bad"):
                # hash() on a str is salted per process, so this used to
                # generate different cases on every run and no two exam
                # results were comparable. Index the dimension instead.
                bars, row = case(d, arm, seed=DIMS.index(d) * 1000 + k)
                out.append(dict(dim=d, k=k, arm=arm, bars=bars, row=row))
    return out
