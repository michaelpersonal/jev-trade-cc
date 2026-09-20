"""Ablation of the sector and macro overlays, plus the walk-forward record.

Both overlays were added to fix the post-2024 breakdown. Neither survives.
This module exists so the negative result is written down rather than
rediscovered: the numbers go into the page, with the walk-forward verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import backtest as B
import data as D
import macro as MAC
import metrics as M
import strategy as S
import universe as U
import walkforward as W

ROOT = Path(__file__).resolve().parent.parent
HALVES = [("full", "2022-01-03", "2026-09-18"),
          ("h1", "2022-01-03", "2024-03-28"),
          ("h2", "2024-04-01", "2026-09-18")]

VARIANTS = [
    ("Baseline: 15% trailing stop", 0, None),
    ("+ macro veto", 1, None),
    ("+ macro symmetric", 2, None),
    ("+ leading groups (top 50%)", 0, 0.50),
    ("+ leading groups (top 25%)", 0, 0.75),
    ("+ macro veto + groups top 50%", 1, 0.50),
    ("+ macro symmetric + groups top 25%", 2, 0.75),
]


def main() -> None:
    sig = pd.read_parquet(ROOT / "data" / "raw" / "signals_grouped.parquet")
    idx, memb, feat = D.index_prices(), U.membership(), MAC.features()
    kw = dict(by_date=B.index_by_date(sig), feat=feat)

    rows = []
    for name, macro, group in VARIANTS:
        S.MAX_POSITIONS, S.PROFIT_TARGET, S.TRAIL_ATR = 5, None, None
        S.TRAIL_PCT, S.MACRO_MODE, S.GROUP_MIN_PCT = 0.15, macro, group
        rec = dict(name=name)
        for lab, a, b in HALVES:
            r = B.run(sig, idx, memb, start=a, end=b, capital=B.CAPITAL, **kw)
            st = M.summarize(r["equity"], r["dates"], "x")
            rec[lab] = st["total_return"]
            if lab == "full":
                rec["max_dd"] = st["max_dd"]
                rec["invested"] = round(
                    100 * sum(1 - d["cash"] / d["equity"] for d in r["daily"])
                    / len(r["daily"]), 0)
        rows.append(rec)

    c = idx["Close"]
    spx = {lab: round(100 * (c.loc[a:b].iloc[-1] / c.loc[a:b].iloc[0] - 1), 1)
           for lab, a, b in HALVES}

    wf = json.loads((ROOT / "data" / "walkforward.json").read_text())
    out = dict(ablation=rows, spx=spx,
               walkforward=dict(
                   folds=wf["folds"],
                   final_wf=wf["final_wf"], final_fixed=wf["final_fixed"],
                   spx=wf["spx"], start=wf["dates"][0][:10], end=wf["dates"][-1][:10],
                   beat=sum(1 for f in wf["folds"] if f["wf"] > f["fixed"]),
                   n=len(wf["folds"]),
                   distinct=len({f["chosen"] for f in wf["folds"]})))
    (ROOT / "data" / "experiments.json").write_text(json.dumps(out))
    print(f"ablation rows: {len(rows)}; walk-forward folds: {out['walkforward']['n']}")
    print(f"  wf ${out['walkforward']['final_wf']:,.0f} vs "
          f"fixed ${out['walkforward']['final_fixed']:,.0f}")


if __name__ == "__main__":
    main()
