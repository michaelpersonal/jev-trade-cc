"""The supported entry point for a Jev-in-the-loop run.

Exists because the previous workflow required a manual `load_panel()` call that
no checked-in caller made, so flipping `JEV_ENTRY` produced a silent all-cash
run. This initialises every input, persists the answer cache, writes the
decision ledger and records the full configuration alongside the result.

  ../.venv/bin/python run_jev.py            # all four configurations
  ../.venv/bin/python run_jev.py --replay   # cache only, fails on a cache miss
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

import backtest as B
import data as D
import jev as J
import macro as MAC
import metrics as M
import strategy as S
import universe as U

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "jev_runs"
CONFIGS = [("rules_only", False, False), ("jev_entries", True, False),
           ("jev_exits", False, True), ("jev_both", True, True)]
SPANS = [("full", "2022-01-03", "2026-09-18"),
         ("h1", "2022-01-03", "2024-03-28"),
         ("h2", "2024-04-01", "2026-09-18")]


def main(replay: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sig = pd.read_parquet(ROOT / "data" / "raw" / "signals_grouped.parquet")
    panel = pd.read_parquet(ROOT / "data" / "raw" / "panel.parquet")
    idx, memb, feat = D.index_prices(), U.membership(), MAC.features()
    B.load_panel(panel)                     # the step that used to be missing
    if replay:
        J.set_offline(True)
    kw = dict(by_date=B.index_by_date(sig), feat=feat)

    print(f"{'configuration':>14} {'full':>9} {'h1':>9} {'h2':>9} {'maxDD':>8} "
          f"{'trades':>7} {'holds':>6} {'errors':>7}")
    print("-" * 82)
    summary = []
    for name, entry, exit_ in CONFIGS:
        S.MAX_POSITIONS, S.PROFIT_TARGET, S.TRAIL_PCT = 5, None, 0.15
        S.TRAIL_ATR, S.MACRO_MODE, S.GROUP_MIN_PCT = None, 0, None
        S.REGIME_MODE, S.YELLOW_SLOTS = 2, None
        S.JEV_ENTRY, S.JEV_EXIT = entry, exit_
        t0 = time.time()
        spans = {}
        for lab, a, b in SPANS:
            r = B.run(sig, idx, memb, start=a, end=b, capital=B.CAPITAL, **kw)
            spans[lab] = M.summarize(r["equity"], r["dates"], lab)
            if lab == "full":
                full = r
        J.save_cache()                       # persist before anything can fail

        if full["jev_errors"]:
            print(f"  !! {name}: {full['jev_errors']} inference failures -- "
                  f"this run is DEGRADED, not a clean comparison")
        rec = dict(name=name, config=full["config"],
                   jev_holds=full["jev_holds"], jev_errors=full["jev_errors"],
                   n_trades=len(full["trades"]),
                   degraded=bool(full["jev_errors"]),
                   **{k: spans[k]["total_return"] for k in spans})
        summary.append(rec)
        pd.DataFrame(full["ledger"]).to_parquet(OUT / f"ledger_{name}.parquet")
        (OUT / f"result_{name}.json").write_text(json.dumps(
            dict(config=full["config"], stats=spans,
                 jev_holds=full["jev_holds"], jev_errors=full["jev_errors"],
                 trades=full["trades"]), default=str))
        print(f"{name:>14} {spans['full']['total_return']:+8.1f}% "
              f"{spans['h1']['total_return']:+8.1f}% {spans['h2']['total_return']:+8.1f}% "
              f"{spans['full']['max_dd']:7.1f}% {len(full['trades']):7d} "
              f"{full['jev_holds']:6d} {full['jev_errors']:7d}   [{time.time()-t0:.0f}s]")
    (OUT / "summary.json").write_text(json.dumps(summary, default=str))
    st = J.stats()
    print(f"\nJev: {st['calls']} calls, {st['hits']} cached, "
          f"{st['input_tokens']:,} input tokens "
          f"(${st['input_tokens']/1e6*0.042:.3f}) | model {J.MODEL}")
    print(f"ledgers and per-config results written to {OUT}")


if __name__ == "__main__":
    main(replay="--replay" in sys.argv)
