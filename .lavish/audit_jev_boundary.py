"""Read-only evidence for the Jev design review. No API calls or data writes.

Run from the repository: .venv/bin/python .lavish/audit_jev_boundary.py
The synthetic timing probe intentionally exposes an existing failure; it is
not a repaired backtest or a new strategy experiment.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import backtest as B
import strategy as S


def main():
    raw = ROOT / "data/raw"
    panel = pd.read_parquet(raw / "panel.parquet")
    signals = pd.read_parquet(raw / "signals_grouped.parquet")
    universe = pd.read_parquet(raw / "universe_pit.parquet")
    entries = pd.read_parquet(raw / "jev_entries.parquet")
    shapes = pd.read_parquet(raw / "jev_shape.parquet")
    members = {d: set(g.ticker) for d, g in universe.groupby("snapshot_date")}
    candidate = entries.merge(
        signals[["date", "ticker", "buyable", "group_pct", "base_len_wk"]],
        on=["date", "ticker"], validate="one_to_one",
    )
    candidate["member"] = [
        t in members[max(s for s in members if s <= d)]
        for d, t in zip(candidate.date, candidate.ticker)
    ]
    regime = S.market_regime(pd.read_parquet(raw / "index__GSPC.parquet"))
    candidate["regime"] = candidate.date.map(regime.regime)
    future_counts = {}
    ordered = panel.sort_values(["ticker", "date"]).copy()
    for horizon in (20, 60):
        ordered["future_close"] = ordered.groupby("ticker").close.shift(-horizon)
        labelled = candidate.merge(
            ordered[["date", "ticker", "future_close"]], on=["date", "ticker"],
            validate="one_to_one",
        )
        future_counts[str(horizon)] = int(labelled.future_close.notna().sum())
    saved = json.loads((ROOT / "data/result.json").read_text())
    exits = [t for t in saved["trades"] if t["side"] == "SELL"
             and t["reason"].startswith("broke 50dma")]

    # Freeze the shipped configuration only inside this isolated process.
    S.MAX_POSITIONS = 5
    S.PROFIT_TARGET = None
    S.TRAIL_PCT = .15
    S.TRAIL_ATR = None
    S.REGIME_MODE = 2
    S.YELLOW_SLOTS = None
    S.MACRO_MODE = 0
    index = pd.DataFrame(
        {"Close": np.linspace(80, 120, 240)},
        index=pd.bdate_range("2021-01-01", periods=240),
    )
    signal_day, fill_day = index.index[-2:]
    synthetic = pd.DataFrame([
        dict(date=d, ticker="TEST", open=100., close=100., high=101.,
             low=99., ma50=90., rs_rating=90., buyable=d == signal_day)
        for d in (signal_day, fill_day)
    ])
    probe = {}
    for label, closing_price in (("original_close", 120.), ("changed_close", 80.)):
        changed = index.copy()
        changed.loc[fill_day, "Close"] = closing_price
        run = B.run(synthetic, changed, {signal_day: {"TEST"}},
                    start=str(signal_day.date()), end=str(fill_day.date()))
        probe[label] = sum(t["side"] == "BUY" for t in run["trades"])

    evidence = {
        "panel": {"rows": len(panel), "tickers": panel.ticker.nunique(),
                  "first": str(panel.date.min().date()),
                  "last": str(panel.date.max().date()),
                  "duplicate_date_ticker_keys": int(panel.duplicated(["date", "ticker"]).sum())},
        "universe": {"tickers": universe.ticker.nunique(),
                     "snapshots": universe.snapshot_date.nunique(),
                     "missing_prices": len(set(universe.ticker) - set(panel.ticker))},
        "jev": {"summary_rows": len(entries), "weekly_rows": len(shapes),
                "distinct_tickers": entries.ticker.nunique(),
                "distinct_dates": entries.date.nunique(),
                "in_snapshot_membership": int(candidate.member.sum()),
                "not_in_snapshot_membership": int((~candidate.member).sum()),
                "buyable": int(candidate.buyable.sum()),
                "member_buyable_nonred": int((candidate.member & candidate.buyable & (candidate.regime != "RED")).sum()),
                "unknown_group": int(candidate.group_pct.isna().sum()),
                "base_length_below_five_weeks": int((candidate.base_len_wk < 5).sum()),
                "full_future_close_horizons_available": future_counts,
                "nonfriday_candidates": int((entries.date.dt.dayofweek != 4).sum())},
        "saved_50dma_exits": {"count": len(exits),
                              "mean_pct": float(np.mean([x["pct"] for x in exits])),
                              "total_realized_pnl": sum(x["pnl"] for x in exits)},
        "ranking": {"days_with_more_candidates_than_open_slots": sum(
            d["open_slots"] > 0 and d["n_cands"] > d["open_slots"]
            for d in saved["daily"])},
        "timing_probe_buy_counts": probe,
        "sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ["src/backtest.py", "src/jev.py", "src/strategy.py",
                         "data/result.json", "data/raw/jev_entries.parquet",
                         "data/raw/jev_shape.parquet"]
        },
    }
    print(json.dumps(evidence, indent=2, default=int))


if __name__ == "__main__":
    main()
