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
    """One exam case. `arm` is 'good' (matches the method) or 'bad'."""
    rng = np.random.default_rng(seed)
    n = WEEKS
    # A default textbook shape: advance, 12% rest, breakout at the pivot.
    adv = np.linspace(72, 100, 6)
    rest = np.concatenate([np.linspace(100, 88, 4), np.linspace(88, 99, 5)])
    closes = np.concatenate([adv, rest, [101.5]])[:n]
    closes = closes * (1 + rng.normal(0, .004, n))
    vols = np.concatenate([np.full(6, 1.0), np.full(9, .62), [1.9]])[:n]
    width = np.concatenate([np.full(6, .012), np.linspace(.020, .008, 9), [.014]])[:n]
    pivot = 100.0

    if dim == "volume" and arm == "bad":
        # identical price path; supply never dries up and the break is quiet
        vols = np.concatenate([np.full(6, 1.0), np.full(9, 1.45), [0.85]])[:n]
    elif dim == "extension" and arm == "bad":
        # same base, but price has already run well beyond the pivot
        closes = np.concatenate([adv, rest, [101.5]])[:n] * (1 + rng.normal(0, .004, n))
        closes[-1] = 118.0
        closes[-2] = 112.0
    elif dim == "tightness" and arm == "bad":
        # same depth and length; ranges stay wide and erratic to the end
        width = np.concatenate([np.full(6, .012), np.full(9, .042), [.040]])[:n]
        closes[6:15] = closes[6:15] * (1 + rng.normal(0, .035, 9))
    elif dim == "advance" and arm == "bad":
        # no prior uptrend: the "base" sits at the bottom of a decline
        closes = np.concatenate([np.linspace(132, 100, 6), rest, [101.5]])[:n]
        closes = closes * (1 + rng.normal(0, .004, n))

    bars = _bars(closes, vols, width)
    # Moving averages, so the prompt's stack line describes these cases too.
    # A "good" arm passes O'Neil's trend template; the no-prior-advance arm
    # genuinely fails it, which is the truth the template line now reports.
    up = not (dim == "advance" and arm == "bad")
    c = float(closes[-1])
    row = dict(pivot=pivot, close=c, rs_rating=88.0,
               hi52=float(max(closes.max(), 101.5)), lo52=float(closes.min()) * .72,
               dollar_vol=140e6, group_pct=0.86, regime="GREEN",
               ma50=c * (0.95 if up else 0.99),
               ma150=c * (0.88 if up else 1.02),
               ma200=c * (0.82 if up else 1.06), ma200_up=up)
    return bars, row


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
