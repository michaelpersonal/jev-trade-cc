"""Ask Jev to judge every breakout candidate in the run.

Deliberately judges all 637 raw breakouts, not the 398 that clear the hand-set
RS>=80 line. The threshold was my choice; letting Jev see the weak ones too is
the point of putting it in the loop.
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

import data as D
import jev as J
import strategy as S

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "jev_entries.parquet"


def main() -> None:
    sig = pd.read_parquet(ROOT / "data" / "raw" / "signals_grouped.parquet")
    reg = S.market_regime(D.index_prices())["regime"]
    c = sig[(sig["date"] >= "2022-01-03") & (sig["date"] <= "2026-09-18")
            & sig["breakout"].fillna(False)].copy()
    c["regime"] = c["date"].map(reg).fillna("yellow")
    c = c.dropna(subset=["rs_rating", "base_len_wk", "hi52", "lo52", "ma50"])
    rows = c.to_dict("records")
    print(f"judging {len(rows)} breakout candidates ...")

    t0 = time.time()
    done = [0]

    def work(r):
        a = J.judge_entry(r)
        done[0] += 1
        if done[0] % 50 == 0:
            print(f"  {done[0]}/{len(rows)}  {time.time()-t0:.0f}s", flush=True)
        return dict(date=r["date"], ticker=r["ticker"],
                    jev_proper=a["proper_base"]["noul"],
                    jev_quality=a["quality"]["score"],
                    jev_quality_conf=a["quality"]["confidence"],
                    jev_follow=a["follow_through"]["noul"])

    with ThreadPoolExecutor(max_workers=8) as ex:
        out = list(ex.map(work, rows))
    J.save_cache()

    df = pd.DataFrame(out)
    df.to_parquet(OUT)
    st = J.stats()
    cost = st["input_tokens"] / 1e6 * 0.042
    print(f"\ndone in {time.time()-t0:.0f}s | {st['calls']} calls, "
          f"{st['hits']} cache hits, {st['input_tokens']:,} input tokens "
          f"(${cost:.3f})")
    print(df[["jev_proper", "jev_quality", "jev_follow"]].describe().round(3).to_string())


if __name__ == "__main__":
    main()
