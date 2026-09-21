"""Jev's refusal must actually refuse.

With JEV_SELECT on, Jev sees the day's candidates and may answer "none".
NEARMISS_MODE draws on the same slots. Before the fix the two ran in
sequence: "none" left pending_buys empty, spare stayed at the full slot
count, and the mechanical near-miss quota bought into every slot Jev had
just declined. Same data, same mocked all-"none" answers, both versions.
"""
import sys, types, importlib.util
sys.path.insert(0, '/Users/michaelguo/projects/jev-trade-cc/src')
import pandas as pd, strategy as S, jev as J, universe as U, data as D

GUARD = "            if S.JEV_SELECT and S.NEARMISS_MODE:"

def load(name, strip_guard):
    src = open('/Users/michaelguo/projects/jev-trade-cc/src/backtest.py').read()
    if strip_guard:                       # restore the pre-fix control flow
        i = src.index(GUARD)
        j = src.index("            if S.NEARMISS_MODE and spare > 0:", i)
        src = src[:i] + src[j:]
        assert "JEV_SELECT and S.NEARMISS_MODE" not in src
    mod = types.ModuleType(name); mod.__file__ = 'backtest.py'
    exec(compile(src, 'backtest.py', 'exec'), mod.__dict__)
    return mod

sig = pd.read_parquet('/Users/michaelguo/projects/jev-trade-cc/data/raw/'
                      'signals_grouped.parquet')
idx, memb = D.index_prices(), U.membership()
pan = D.panel([])

S.JEV_SELECT, S.NEARMISS_MODE = True, 3
S.JEV_ENTRY = S.JEV_EXIT = False
J.set_offline(True)
J.ask = lambda state, qs, tag: {"pick": {"choice": "none", "confidence": 0.9}}

for label, strip in (("before the fix", True), ("after the fix", False)):
    B = load(f"bt_{strip}", strip)
    B.load_panel(pan); B.load_assessments(pd.read_parquet('/Users/michaelguo/projects/jev-trade-cc/data/raw/jev_assessments.parquet'))
    r = B.run(sig, idx, memb, start="2022-01-03", end="2022-12-30")
    buys = len(r["trades"])
    print(f"  {label:<16} Jev answered 'none' every day -> {buys:3d} buys, "
          f"final ${r['equity'][-1]:,.0f}")
    globals()[f"n_{strip}"] = buys

print()
assert n_True > 0, "defect did not reproduce"
assert n_False == 0, f"refusal still overridden: {n_False} buys"
print(f"  PASS: the defect bought {n_True} times against an explicit refusal; "
      f"the fix buys 0.")
