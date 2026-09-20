"""Evaluation 3: does acting on Jev's judgment improve anything?

Executes `src/policy_contract.md` exactly as frozen. Entry is the first
session open strictly after the filing became public, so the announcement move
is deliberately forgone -- the question is whether anything is left afterwards.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
HORIZONS = (1, 5, 20)
COST = 0.0010          # 10 bp round trip
RNG = np.random.default_rng(20260920)


def build_events() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data" / "guidance_corpus.parquet")
    jv = pd.read_parquet(ROOT / "data" / "jev_guidance.parquet")
    df = df.merge(jv, on="bid").dropna(subset=["ticker", "acceptance"])
    px = pd.read_parquet(ROOT / "data" / "event_prices.parquet")
    sessions = pd.DatetimeIndex(sorted(px.loc[px.ticker == "SPY", "date"].unique()))
    by = {t: g.set_index("date").sort_index() for t, g in px.groupby("ticker")}
    spy = by["SPY"]

    rows = []
    for r in df.itertuples():
        # EDGAR stamps acceptance in Eastern time despite the trailing Z.
        acc = pd.Timestamp(r.acceptance).tz_localize(None)
        # First session that OPENS strictly after the filing was public.
        day = acc.normalize()
        if acc.time() >= pd.Timestamp("09:30").time():
            day = day + pd.Timedelta(days=1)
        i = sessions.searchsorted(day, side="left")
        if i >= len(sessions):
            continue
        entry_date = sessions[i]
        g = by.get(r.ticker)
        if g is None or entry_date not in g.index:
            continue
        gi = g.index.get_loc(entry_date)
        si = spy.index.get_loc(entry_date)
        rec = dict(bid=r.bid, ticker=r.ticker, population=r.population,
                   gold=r.claude == "yes", lex=r.lex == "yes",
                   jev=float(r.jev_noul), entry_date=entry_date,
                   lag_days=(entry_date - acc.normalize()).days)
        o = float(g["open"].iloc[gi])
        so = float(spy["open"].iloc[si])
        ok = True
        for h in HORIZONS:
            if gi + h - 1 >= len(g) or si + h - 1 >= len(spy):
                ok = False
                break
            c = float(g["close"].iloc[gi + h - 1])
            sc = float(spy["close"].iloc[si + h - 1])
            rec[f"ex{h}"] = (c / o - 1) - (sc / so - 1)
        if ok and np.isfinite(o) and o > 0:
            rows.append(rec)
    return pd.DataFrame(rows)


def summarise(ev: pd.DataFrame) -> None:
    print(f"tradeable events: {len(ev)}  gold positives: {int(ev.gold.sum())}  "
          f"issuers: {ev.ticker.nunique()}")
    print(f"entry lag (calendar days after filing): median "
          f"{ev.lag_days.median():.0f}, max {ev.lag_days.max():.0f}\n")

    signals = {
        "Jev noul >= 0.80": (ev.jev >= 0.80).to_numpy(),
        "Gold label (ceiling)": ev.gold.to_numpy(),
        "Regex lexicon": ev.lex.to_numpy(),
        "All events (base rate)": np.ones(len(ev), bool),
    }
    print(f"{'signal':>24} {'n':>4} " +
          " ".join(f"{'ex'+str(h):>20}" for h in HORIZONS))
    for name, m in signals.items():
        cells = []
        for h in HORIZONS:
            x = ev.loc[m, f"ex{h}"].to_numpy() - COST
            if len(x) < 2:
                cells.append(f"{'-':>20}")
                continue
            se = x.std(ddof=1) / np.sqrt(len(x))
            cells.append(f"{100*x.mean():+7.2f}% +/-{100*1.96*se:5.2f}")
        print(f"{name:>24} {int(m.sum()):>4} " + " ".join(cells))

    # The null: a random signal firing at the same rate.
    fire = int((ev.jev >= 0.80).sum())
    print(f"\nnull distribution -- {fire} events drawn at random, 1000 times:")
    for h in HORIZONS:
        x = ev[f"ex{h}"].to_numpy() - COST
        draws = np.array([RNG.choice(x, fire, replace=False).mean()
                          for _ in range(1000)])
        obs = x[(ev.jev >= 0.80).to_numpy()].mean()
        lo, hi = np.percentile(draws, [2.5, 97.5])
        pct = (draws <= obs).mean()
        verdict = "OUTSIDE" if (obs < lo or obs > hi) else "inside"
        print(f"  ex{h:<2}  observed {100*obs:+6.2f}%   null 95% "
              f"[{100*lo:+6.2f}%, {100*hi:+6.2f}%]   pctile {100*pct:5.1f}  -> {verdict}")

    print("\nby population (no cost, raw excess):")
    print(ev.groupby("population")[[f"ex{h}" for h in HORIZONS]]
          .agg(["size", "mean"]).round(4).to_string())


if __name__ == "__main__":
    ev = build_events()
    ev.to_parquet(ROOT / "data" / "decision_events.parquet")
    summarise(ev)
