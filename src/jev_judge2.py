"""Judge every candidate again, this time showing Jev the weekly bars."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

import data as D
import jev as J
import strategy as S

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "jev_shape.parquet"
WEEKS = 16


def main() -> None:
    sig = pd.read_parquet(ROOT / "data" / "raw" / "signals_grouped.parquet")
    pan = pd.read_parquet(ROOT / "data" / "raw" / "panel.parquet")
    reg = S.market_regime(D.index_prices())["regime"]

    # per-ticker volume baseline once, rather than inside the loop
    pan = pan.sort_values(["ticker", "date"])
    pan["vol_rel"] = pan["volume"] / pan.groupby("ticker")["volume"].transform(
        lambda v: v.rolling(50).mean())
    px_by_ticker = {t: g for t, g in pan.groupby("ticker")}

    c = sig[(sig["date"] >= "2022-01-03") & (sig["date"] <= "2026-09-18")
            & sig["breakout"].fillna(False)].copy()
    c["regime"] = c["date"].map(reg).fillna("yellow")
    c = c.dropna(subset=["rs_rating", "pivot", "hi52", "lo52"])
    rows = c.to_dict("records")
    print(f"judging {len(rows)} candidates on their weekly bars ...")

    t0, done = time.time(), [0]

    def bars_for(r):
        g = px_by_ticker[r["ticker"]]
        g = g[g["date"] <= r["date"]].tail(260)          # a year of dailies
        w = g.set_index("date").resample("W").agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"),
            close=("close", "last"), vol_rel=("vol_rel", "mean")).dropna()
        return w.tail(WEEKS)

    def work(r):
        w = bars_for(r)
        if len(w) < 8:
            return None
        a = J.judge_shape(r, w)
        done[0] += 1
        if done[0] % 100 == 0:
            print(f"  {done[0]}/{len(rows)}  {time.time()-t0:.0f}s", flush=True)
        return dict(date=r["date"], ticker=r["ticker"], weeks=len(w),
                    shape_proper=a["proper_base"]["noul"],
                    shape_quality=a["quality"]["score"],
                    shape_quality_conf=a["quality"]["confidence"],
                    shape_follow=a["follow_through"]["noul"])

    with ThreadPoolExecutor(max_workers=8) as ex:
        out = [x for x in ex.map(work, rows) if x]
    J.save_cache()
    df = pd.DataFrame(out)
    df.to_parquet(OUT)
    st = J.stats()
    print(f"\ndone in {time.time()-t0:.0f}s | {st['calls']} calls, "
          f"{st['input_tokens']:,} input tokens (${st['input_tokens']/1e6*0.042:.3f})")
    print(df[["shape_proper", "shape_quality", "shape_follow"]].describe().round(3).to_string())


if __name__ == "__main__":
    main()
