"""Phase A of stock selection: Jev assesses every eligible candidate.

Code keeps only mandatory constraints -- index membership on the date, price
above $10, turnover above $20M/day, price above its 200-day average (O'Neil's
own requirement that the stock be in an uptrend) -- plus the factual event of a
close above the prior 13-week high. Roughly 22 names a day.

Every quality question O'Neil asks is Jev's to answer, not a threshold here.
"""
from __future__ import annotations

import json
import sys, time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

import backtest as B
import data as D
import jev as J
import strategy as S
import universe as U

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "jev_assessments.parquet"


def eligible(sig: pd.DataFrame) -> pd.DataFrame:
    w = sig[(sig["date"] >= "2022-01-03") & (sig["date"] <= "2026-09-18")]
    m = ((w["close"] >= S.MIN_PRICE) & (w["dollar_vol"] >= S.MIN_DOLLAR_VOL)
         & (w["close"] > w["ma200"]) & w["ma200"].notna()
         & (w["close"] > w["pivot"]) & w["pivot"].notna()
         & w["rs_rating"].notna())
    return w[m]


def main(limit: int | None = None, sample: int | None = None) -> None:
    """`sample` draws a fixed-seed random sample instead of running the pool.

    A full pass is 22,398 requests and about $1.60. The criteria prose is the
    part of this system that actually gets iterated, so validating a wording
    change against the whole pool means paying for the whole pool every time.
    A 500-row sample costs about four cents and is enough to see a label
    distribution move. `limit` takes the FIRST n rows, which are all 2022 and
    therefore one market; prefer `sample`. Sample runs write to their own file
    and never overwrite the real assessments.
    """
    sig = pd.read_parquet(ROOT / "data" / "raw" / "signals_grouped.parquet")
    B.load_panel(pd.read_parquet(ROOT / "data" / "raw" / "panel.parquet"))
    reg = S.market_regime(D.index_prices())["regime"]
    memb = U.membership()

    c = eligible(sig).copy()
    c["regime"] = c["date"].map(reg).fillna("YELLOW")
    keep = [i for i, r in zip(c.index, c.itertuples())
            if r.ticker in B.memb_on(r.date, memb)]
    c = c.loc[keep]
    if sample:
        c = c.sample(min(sample, len(c)), random_state=0).sort_values("date")
    rows = c.to_dict("records")
    if limit:
        rows = rows[:limit]
    print(f"assessing {len(rows):,} eligible candidates "
          f"({len(rows)/c['date'].nunique():.1f}/day)"
          + (f"  [SAMPLE of {len(rows)}, seed 0]" if sample else ""),
          flush=True)

    t0, done = time.time(), [0]
    # Failures used to return None, which is also what "not enough history"
    # returns. A stale option set therefore rejected every "faulty" answer and
    # dropped 8,848 rows in silence -- the assessment file simply contained no
    # faulty setups, and nothing said why. Count the two apart.
    nohist, failed = [0], {}

    def work(r):
        base = dict(date=r["date"], ticker=r["ticker"])
        bars = B.weekly_bars(r["ticker"], r["date"])
        if bars is None or len(bars) < 8:
            nohist[0] += 1
            return dict(base, status="no_history", setup=None, conf=None,
                        supply=None, prior_advance=None, pattern=None,
                        pattern_conf=None)
        try:
            a = J.assess(r, bars)
            out = dict(base,
                       setup=J.choice_of(a, "setup",
                                         set(J.ASSESS["setup"].criteria)),
                       conf=a["setup"].get("confidence"),
                       supply=a["supply"]["noul"],
                       prior_advance=a["prior_advance"]["noul"],
                       pattern=J.choice_of(a, "pattern",
                                           set(J.ASSESS["pattern"].criteria)),
                       pattern_conf=a["pattern"].get("confidence"),
                       status="ok")
        except Exception as exc:
            k = f"{type(exc).__name__}: {str(exc)[:70]}"
            failed[k] = failed.get(k, 0) + 1
            return dict(base, status="error", setup=None, conf=None,
                        supply=None, prior_advance=None, pattern=None,
                        pattern_conf=None)
        done[0] += 1
        if done[0] % 2000 == 0:
            print(f"  {done[0]:,}/{len(rows):,}  {time.time()-t0:.0f}s", flush=True)
            J.save_cache()
        return out

    with ThreadPoolExecutor(max_workers=10) as ex:
        res = [x for x in ex.map(work, rows) if x]
    J.save_cache()
    df = pd.DataFrame(res)
    partial = bool(sample or limit)
    out = (OUT.with_name("jev_assessments_sample.parquet") if partial else OUT)
    df.to_parquet(out)
    # A partial run must not be able to masquerade as the production dataset:
    # `main(limit)` used to write OUT directly, so a 200-row smoke test could
    # silently replace a 22,398-row artifact and the backtest would read it
    # as a complete universe.
    manifest = dict(
        artifact=out.name,
        question_fingerprint=J.question_fingerprint(J.ASSESS, "assess"),
        model=J.MODEL,
        partial=partial,
        requested=len(rows),
        returned=len(df),
        ok=int((df["status"] == "ok").sum()) if len(df) else 0,
        no_history=nohist[0],
        errors=sum(failed.values()),
        error_kinds=failed,
        written_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2), flush=True)
    print(f"\ndone in {time.time()-t0:.0f}s | {len(df):,} assessments "
          f"| ${J.stats()['input_tokens']/1e6*0.042:.2f}", flush=True)
    print(f"dropped: {nohist[0]:,} without enough weekly history, "
          f"{sum(failed.values()):,} failed", flush=True)
    for k, n in sorted(failed.items(), key=lambda kv: -kv[1]):
        print(f"    {n:>6,}  {k}", flush=True)
    print(df["setup"].value_counts().to_string(), flush=True)
    print(df["setup"].value_counts().to_string(), flush=True)


if __name__ == "__main__":
    av = sys.argv[1:]
    if av and av[0] == "--sample":
        main(sample=int(av[1]) if len(av) > 1 else 500)
    else:
        main(int(av[0]) if av else None)
