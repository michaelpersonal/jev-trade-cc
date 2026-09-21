"""The fixed four-arm comparison, as a committed runner.

This table used to live in an ad-hoc shell driver in /tmp, which meant the
headline number in the README came from a script nobody could re-run. The
arms are fixed here and are not to be selected on their results: rules only,
Jev filtering the rule-built pool, Jev choosing from the pool, and Jev doing
both. Every arm uses identical data, dates, capital and stops.
"""
from __future__ import annotations

import json
import sys
import time

import pandas as pd

import backtest as B
import data as D
import jev as J
import strategy as S
import universe as U

ROOT = B.ROOT

# The shipped configuration. These three values decide the headline number and
# they were never in strategy.py: they were assigned at runtime by a shell
# driver in /tmp that no longer exists, so a clone of this repository
# reproduced the literal O'Neil rules ($112,992) and not the published result.
# strategy.py keeps O'Neil's own numbers as written; the deviations from them
# are declared here, in the runner, where they can be read and re-run.
SHIPPED = dict(
    PROFIT_TARGET=None,   # O'Neil's fixed 20-25% target, measured as the most
                          # damaging single rule in this system
    TRAIL_PCT=0.15,       # replaces it: give back 15% of the peak close
    MAX_POSITIONS=5,
)


def apply_shipped() -> None:
    for k, v in SHIPPED.items():
        setattr(S, k, v)


ARMS = [
    # label                          ENTRY  EXIT  SELECT  NEARMISS
    ("rules only (no Jev)",          False, False, False, 3),
    ("Jev filters the rule pool",    True,  True,  False, 3),
    ("Jev selects from the pool",    False, False, True,  3),
    ("Jev selects, filters and exits", True, True,  True,  3),
]


def main(arms=None) -> None:
    sig = pd.read_parquet(ROOT / "data" / "raw" / "signals_grouped.parquet")
    idx, memb = D.index_prices(), U.membership()
    B.load_panel(pd.read_parquet(ROOT / "data" / "raw" / "panel.parquet"))
    ap = ROOT / "data" / "raw" / "jev_assessments.parquet"
    B.load_assessments(pd.read_parquet(ap), json.loads(
        ap.with_suffix(".manifest.json").read_text()))

    spx = idx["Close"]
    spx = spx[(spx.index >= B.START) & (spx.index <= B.END)]
    bench = B.CAPITAL * spx.iloc[-1] / spx.iloc[0]

    apply_shipped()
    print("shipped config: " + ", ".join(f"{k}={v}" for k, v in SHIPPED.items()))
    print(f"{'arm':<32}{'final':>12}{'profit':>11}{'maxDD':>8}"
          f"{'trades':>8}{'asks':>7}{'secs':>7}")
    print("-" * 85)
    for label, ent, ext, sel, nm in (arms or ARMS):
        apply_shipped()
        S.JEV_ENTRY, S.JEV_EXIT = ent, ext
        S.JEV_SELECT, S.NEARMISS_MODE = sel, nm
        st = J.stats(); c0 = st["calls"] + st["hits"]; t0 = time.time()
        r = B.run(sig, idx, memb)
        eq = pd.Series(r["equity"])
        dd = (eq / eq.cummax() - 1).min() * 100
        print(f"{label:<32}${eq.iloc[-1]:>11,.0f}${eq.iloc[-1]-B.CAPITAL:>10,.0f}"
              f"{dd:>7.1f}%{len(r['trades']):>8}"
              f"{sum(J.stats()[k] for k in ('calls', 'hits'))-c0:>7}"
              f"{time.time()-t0:>6.0f}s")
        J.save_cache()
    print("-" * 85)
    print(f"{'S&P 500 buy and hold':<32}${bench:>11,.0f}"
          f"${bench-B.CAPITAL:>10,.0f}")
    print(f"\ntotal spend this run "
          f"${J.stats()['input_tokens']/1e6*0.042:.3f}")


if __name__ == "__main__":
    if len(sys.argv) > 1:                    # run one arm by index
        main([ARMS[int(sys.argv[1])]])
    else:
        main()
