"""Guards for the carried contract: anchor, policy, artifact provenance.

Each test is written to FAIL against the defect it describes. A test that
passes because nothing happened is not a test; every case below forces the
situation first and then asserts on it.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '/Users/michaelguo/projects/jev-trade-cc/src')
import anchor as A            # noqa: E402
import backtest as B          # noqa: E402
import jev as J               # noqa: E402
import policy as P            # noqa: E402
import strategy as S          # noqa: E402

ok = True


def check(label, cond, detail=""):
    global ok
    ok = ok and bool(cond)
    print(f"  {label}: {'PASS' if cond else 'FAIL'}{'  ' + detail if detail else ''}")


print("anchor is frozen at the decision:")
# A real breakout, then the rolling pivot climbing away from it.
sig = pd.read_parquet('../data/raw/signals_grouped.parquet')
w = sig[(sig.date >= '2022-01-03') & (sig.date <= '2026-09-18')]
b = w[w["buyable"].fillna(False)].sort_values("date").iloc[40]
later = w[(w.ticker == b["ticker"]) & (w.date > b["date"])].sort_values("date")
lt = later.iloc[89]
anc = A.from_row(b, b["ticker"], b["date"], "screen")

frozen = anc.distance_pct(lt["close"])
rolling = (lt["close"] / lt["pivot"] - 1) * 100
check("the two references disagree", abs(frozen - rolling) > 1.0,
      f"frozen {frozen:+.1f}% vs rolling {rolling:+.1f}%")
check("anchor holds the entry base", anc.base_top == b["pivot"])
check("rolling pivot has moved", lt["pivot"] != b["pivot"],
      f"{b['pivot']:.2f} -> {lt['pivot']:.2f}")

# and the position carries it
pos = B.Position(b["ticker"], 10, float(b["close"]), b["date"], 0, anc)
check("position carries the anchor", pos.anchor is anc)
check("a position without one degrades, not crashes",
      B.Position("X", 1, 1.0, b["date"], 0).anchor is None)

print("\npolicy resolves once and the call sites cannot disagree:")
saved = (S.JEV_EXIT, S.JEV_EXIT_MODE, S.JEV_SELECT, S.NEARMISS_MODE)
S.JEV_EXIT, S.JEV_EXIT_MODE = False, 2
check("JEV_EXIT off silences mode 2", P.resolve().exit_path == "none")
check("and says so", any("overrides" in n for n in P.resolve().notes))
S.JEV_EXIT, S.JEV_EXIT_MODE = True, 0
check("mode 0 silences the override", P.resolve().exit_path == "none")
S.JEV_EXIT, S.JEV_EXIT_MODE = True, 1
check("mode 1 is the override path", P.resolve().exit_path == "override")
S.JEV_EXIT_MODE = 2
check("mode 2 is the review path", P.resolve().exit_path == "review")
S.JEV_SELECT, S.NEARMISS_MODE = True, 3
check("selection disables the near-miss path", P.resolve().nearmiss_mode == 0)
rec = P.resolve().as_record()
for k in ("exit_path", "jev_select", "review_every", "nearmiss_mode",
          "jev_entry", "defer_max", "review_abstain"):
    check(f"config records {k}", k in rec)
(S.JEV_EXIT, S.JEV_EXIT_MODE, S.JEV_SELECT, S.NEARMISS_MODE) = saved

print("\nthe exit prompt is built from the anchor, not the tape:")
row = dict(close=float(lt["close"]), ma50=float(lt["close"]) * 1.04,
           ma200=float(lt["close"]) * 0.9, hi52=float(lt["close"]) * 1.3,
           rs_rating=72, regime="GREEN")
txt = J.describe_position(row, gain_pct=-4, days_held=90, peak_gain_pct=12,
                          below_ma_days=2, sessions_left=3,
                          stop_distance_pct=3.1,
                          pivot_distance_pct=anc.distance_pct(lt["close"]))
line = [l for l in txt.split("\n") if "top of the base" in l]
check("prompt states the frozen distance", line
      and f"{frozen:+.1f}%" in line[0], line[0].strip() if line else "missing")



# --------------------------------------------------------------------------
# Autonomous exit mode: the declared policy must be the executed one.
# --------------------------------------------------------------------------
print("\nautonomous exit mode (JEV_EXIT_MODE=2):")
import compare as C          # noqa: E402
import data as D             # noqa: E402
import universe as U         # noqa: E402

_sig = pd.read_parquet('../data/raw/signals_grouped.parquet')
_idx, _memb = D.index_prices(), U.membership()
_pan = pd.read_parquet('../data/raw/panel.parquet')


def _run(answer, *, raises=False, end="2023-06-30"):
    """Run the real loop with every review answered the same way."""
    B.load_panel(_pan)
    B.load_fundamentals(None)
    C.apply_shipped()
    S.JEV_ENTRY, S.JEV_EXIT = False, True
    S.JEV_EXIT_MODE, S.JEV_SELECT, S.NEARMISS_MODE = 2, False, 3
    real = J.ask

    def fake(state, questions, kind):
        if kind.startswith("holding_review"):
            if raises:
                raise J.JevUnavailable("simulated outage")
            return {"action": {"choice": answer, "confidence": 0.9,
                               "probabilities": {answer: 0.9}}}
        return real(state, questions, kind)
    J.ask = fake
    try:
        return B.run(_sig, _idx, _memb, start="2022-01-03", end=end)
    finally:
        J.ask = real


r_unclear = _run("unclear")
led = pd.DataFrame(r_unclear["ledger"])
rev = led[led["kind"] == "review"]
check("abstentions are recorded as abstentions, not as holds",
      (rev["status"] == "abstain").any(),
      f"{(rev['status']=='abstain').sum()} abstain rows")
check("repeated abstention hands the decision back",
      (rev["status"] == "abstain_expired").any(),
      f"{(rev['status']=='abstain_expired').sum()} expiries")
runs = rev[rev["status"] == "abstain_expired"]["value"]
check("and only after the declared limit",
      bool(len(runs)) and int(runs.max()) == S.ABSTAIN_MAX + 1,
      f"expired at {int(runs.max()) if len(runs) else '-'} "
      f"(ABSTAIN_MAX={S.ABSTAIN_MAX})")

r_hold = _run("hold")
led_h = pd.DataFrame(r_hold["ledger"])
check("a confident hold is NOT bounded",
      not (led_h[led_h["kind"] == "review"]["status"] == "abstain_expired").any(),
      "holding a leader for months is the strategy working")

r_err = _run("hold", raises=True)
led_e = pd.DataFrame(r_err["ledger"])
erows = led_e[(led_e["kind"] == "review") & (led_e["status"] == "error")]
check("an inference failure is recorded as an error", len(erows) > 0,
      f"{len(erows)} errors")
check("and is NOT credited to Jev as a hold",
      bool(len(erows)) and (erows["action"] == erows["baseline"]).all(),
      "action equals the mechanical baseline")
check("a run that could not infer is marked incomplete",
      r_err["incomplete"] is True,
      f"error_rate {r_err['error_rate']:.0%}")
check("a run that could infer is not", r_unclear["incomplete"] is False)

print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
sys.exit(0 if ok else 1)
