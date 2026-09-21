"""Cheap sample proof that the "what day is today" fixes worked.

Run this BEFORE spending on a full pass. About $0.06.

The two failures being tested are distinct and have opposite signatures:

  A  missing state    -> flat distribution, forced pick. Diagnosed at
                         `pattern` confidence 0.257 against 0.200 uniform,
                         45.4% of Nouls within +/-0.15 of 0.50, and exit
                         confidence 0.38 against 0.33 uniform.
  B  premise in state -> confident agreement with a handed conclusion.
                         Diagnosed at 2.4% keep rate / 0.90 confidence under
                         the override framing against 46.0% / 0.38 neutral.

PREDICTIONS ARE REGISTERED BELOW, BEFORE THE RUN. They are recorded in git so
a disappointing result cannot be reinterpreted afterwards as a success.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import anchor as A
import backtest as B
import compare as C
import data as D
import jev as J
import jev_select as JS
import strategy as S
import universe as U

# --- pre-registered baselines, measured on the code before these fixes ----
BASE = {
    "pattern_conf":  0.257,   # vs 0.200 uniform over 5 options
    "setup_conf":    0.385,   # vs 0.250 uniform over 4 (extended removed)
    "noul_undecided": 0.454,  # fraction within +/-0.15 of 0.50
    "exit_keep":     0.024,   # override framing
    "exit_conf":     0.90,    # override framing: confident agreement
    "neutral_keep":  0.460,   # neutral framing, the honest reference
    "neutral_conf":  0.38,    # vs 0.33 uniform over 3 options
}
PREDICT = """
A. entry state (daily bars, base count, earnings)
   pattern confidence RISES above 0.257 and clears 0.200 uniform by more
   undecided Nouls FALL below 0.454
   -> if these do not move, the added text is words, not evidence

B. exit framing (mode 2, neutral question)
   keep rate LANDS NEAR 0.46, not 0.024
   confidence LANDS NEAR 0.38, not 0.90
   -> 0.90 confidence again would mean the premise is still being handed over

B2. exit state (earnings, RS direction, down-day volume, holding summary)
   neutral confidence RISES above 0.38 and clears 0.33 uniform by more
   -> this is the only number that can show the exit EVIDENCE helped, as
      distinct from the exit FRAMING
"""
N = 300


def verdict(name, got, base, direction):
    arrow = "rises" if direction > 0 else "falls"
    good = (got > base) if direction > 0 else (got < base)
    print(f"  {name:<22} {base:.3f} -> {got:.3f}   "
          f"{'MOVED as predicted' if good else 'DID NOT ' + arrow.upper()}")
    return good


def main() -> None:
    print(__doc__)
    print("REGISTERED PREDICTIONS:" + PREDICT)
    sig = pd.read_parquet(C.ROOT / "data" / "raw" / "signals_grouped.parquet")
    pan = pd.read_parquet(C.ROOT / "data" / "raw" / "panel.parquet")
    fp = C.ROOT / "data" / "raw" / "fundamentals.parquet"
    B.load_panel(pan)
    B.load_fundamentals(pd.read_parquet(fp) if fp.exists() else None)

    # ---- A: entry state -------------------------------------------------
    print("\nA. entry state, %d sampled candidates" % N)
    JS.main(sample=N)
    d = pd.read_parquet(C.ROOT / "data" / "raw" /
                        "jev_assessments_sample.parquet")
    d = d[d["status"] == "ok"]
    nou = np.concatenate([d["supply"].to_numpy(), d["prior_advance"].to_numpy()])
    a1 = verdict("pattern confidence", d["pattern_conf"].mean(),
                 BASE["pattern_conf"], +1)
    a2 = verdict("undecided Nouls", float(np.mean(np.abs(nou - .5) < .15)),
                 BASE["noul_undecided"], -1)

    # ---- B: exit framing and exit state ---------------------------------
    print("\nB. exit framing and evidence, on real weakened positions")
    idx, memb = D.index_prices(), U.membership()
    C.apply_shipped()
    S.JEV_ENTRY, S.JEV_EXIT = False, True
    S.JEV_SELECT, S.NEARMISS_MODE = False, 3
    r = B.run(sig, idx, memb, start="2022-01-03", end="2023-12-29")
    led = pd.DataFrame(r["ledger"])
    rev = led[led["kind"] == "review"]
    rev = rev[rev["status"].isin(["ok", "abstain"])]
    keep = float((rev["action"] == "hold").mean()) if len(rev) else float("nan")
    conf = np.nanmean([x for x in rev.get("conf", pd.Series(dtype=float))]) \
        if "conf" in rev else float("nan")
    print(f"  reviews answered       {len(rev)}")
    print(f"  keep rate              {BASE['exit_keep']:.3f} (override) -> "
          f"{keep:.3f}   target ~{BASE['neutral_keep']:.2f}")
    b1 = keep > 0.20
    print(f"  {'KEEP RATE RECOVERED' if b1 else 'STILL COLLAPSED -- premise still handed over'}")
    print(f"  run incomplete?        {r['incomplete']}  "
          f"(error rate {r['error_rate']:.1%})")

    print("\nsummary")
    for lab, good in (("A entry state", a1 and a2), ("B exit framing", b1)):
        print(f"  {lab:<18} {'SUPPORTED' if good else 'NOT SUPPORTED'}")
    print(f"\nspend ${J.stats()['input_tokens']/1e6*0.042:.3f}")
    J.save_cache()


if __name__ == "__main__":
    main()
