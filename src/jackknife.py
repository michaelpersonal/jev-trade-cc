"""Sensitivity of the ARMS' DIFFERENCE to universe composition.

An earlier version of this measured the dispersion of rules-only equity under
deletion and multiplied its standard deviation by 1.96. That was wrong twice
over: deleting observed survivors does not sample the unknown missing-data
mechanism, so the number is not a confidence interval for that bias; and
comparing a single arm's dispersion against Jev's incremental effect compares
two different quantities. Common shocks hit both arms and largely cancel.

The relevant statistic is the PAIRED difference -- Jev equity minus rules
equity on the SAME deleted panel -- and its dispersion across draws. That is
what this measures. It remains a sensitivity analysis of a deletion procedure,
not an estimate of the survivorship bias itself.
"""
from __future__ import annotations

import random
import sys

import numpy as np
import pandas as pd

import backtest as B
import compare as C
import data as D
import jev as J
import strategy as S
import universe as U

N_DRAWS = int(sys.argv[1]) if len(sys.argv) > 1 else 12
DROP_N = 49


def arm(sig, idx, memb, pan, *, jev: bool) -> float:
    C.apply_shipped()
    S.JEV_ENTRY = S.JEV_EXIT = jev
    S.JEV_SELECT = False
    S.NEARMISS_MODE = 3
    B.load_panel(pan)
    return B.run(sig, idx, memb)["equity"][-1]


def main() -> None:
    pan = pd.read_parquet(C.ROOT / "data" / "raw" / "panel.parquet")
    fp = C.ROOT / "data" / "raw" / "fundamentals.parquet"
    B.load_fundamentals(pd.read_parquet(fp) if fp.exists() else None)
    memb, idx = U.membership(), D.index_prices()
    have = sorted(pan["ticker"].unique())

    def pair(drop):
        p = pan[~pan["ticker"].isin(drop)]
        sig = S.build_signals(p, membership=memb)
        return arm(sig, idx, memb, p, jev=False), arm(sig, idx, memb, p, jev=True)

    r0, j0 = pair(set())
    print(f"undeleted panel: rules ${r0:,.0f}  jev ${j0:,.0f}  "
          f"diff ${j0-r0:+,.0f}\n")

    rng = random.Random(0)
    rows = []
    for k in range(N_DRAWS):
        r, j = pair(set(rng.sample(have, DROP_N)))
        rows.append((r, j, j - r))
        print(f"  draw {k+1:>2}: rules ${r:>9,.0f}  jev ${j:>9,.0f}  "
              f"diff ${j-r:>+9,.0f}", flush=True)
        J.save_cache()

    a = np.array(rows)
    rules, jev, diff = a[:, 0], a[:, 1], a[:, 2]
    print(f"\n{'':<22}{'mean':>12}{'sd':>11}{'min':>12}{'max':>12}")
    for lab, v in (("rules-only equity", rules), ("jev equity", jev),
                   ("PAIRED diff", diff)):
        print(f"{lab:<22}${v.mean():>11,.0f}${v.std(ddof=1):>10,.0f}"
              f"${v.min():>11,.0f}${v.max():>11,.0f}")
    print(f"\nsd of each arm separately  ~${rules.std(ddof=1):,.0f}")
    print(f"sd of the paired difference ${diff.std(ddof=1):,.0f}")
    print(f"draws where Jev beat rules: {(diff > 0).sum()}/{len(diff)}")
    print(f"\nspend ${J.stats()['input_tokens']/1e6*0.042:.3f}")


if __name__ == "__main__":
    main()
