"""Point-in-time GICS classification, from the same Wikipedia revisions.

O'Neil held that roughly half of a stock's move comes from its industry group,
which is why IBD ranks 197 groups by relative strength. We need to know which
group a stock belonged to *on a given date*, so the classification is read from
the same historical revisions the membership came from -- never from today's
table, which would quietly reclassify companies backwards in time.

Output: data/raw/sectors_pit.parquet  [snapshot_date, ticker, sector, industry]
"""
from __future__ import annotations

import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from universe import API, PAGES, SNAPSHOTS, UA, _clean, _get

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CACHE = RAW / "sector_snaps"
CACHE.mkdir(parents=True, exist_ok=True)
OUT = RAW / "sectors_pit.parquet"

REVS = RAW / "revids.csv"          # cache revision ids so retries stay cheap


def _revids() -> dict[tuple[str, str], int]:
    if REVS.exists():
        d = pd.read_csv(REVS)
        return {(r.group, r.snap): int(r.revid) for r in d.itertuples()}
    return {}


def _save_revids(m: dict) -> None:
    pd.DataFrame([{"group": g, "snap": s, "revid": v} for (g, s), v in m.items()]
                 ).to_csv(REVS, index=False)


def _revision_at(title: str, when: pd.Timestamp) -> int | None:
    r = _get(API, params={
        "action": "query", "prop": "revisions", "titles": title, "rvlimit": 1,
        "rvstart": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "rvdir": "older",
        "rvprop": "ids", "format": "json"}).json()
    page = next(iter(r["query"]["pages"].values()))
    revs = page.get("revisions")
    return revs[0]["revid"] if revs else None


def _flat(col) -> str:
    return (str(col[0]) if isinstance(col, tuple) else str(col)).strip().lower()


def _classify(html: str, lo: int, hi: int) -> pd.DataFrame | None:
    """Pull [ticker, sector, industry] out of whichever table is the roster."""
    best = None
    for tab in pd.read_html(StringIO(html)):
        if not (lo <= len(tab) <= hi):
            continue
        cols = {_flat(c): c for c in tab.columns}
        tcol = next((cols[k] for k in cols if k in ("symbol", "ticker")), None)
        scol = next((cols[k] for k in cols if "gics sector" in k), None)
        icol = next((cols[k] for k in cols if "sub-industry" in k
                     or "gics sub" in k), None)
        if tcol is None or scol is None:
            continue
        out = pd.DataFrame({
            "ticker": [_clean(v) for v in tab[tcol]],
            "sector": tab[scol].astype(str).str.strip(),
            "industry": (tab[icol].astype(str).str.strip() if icol is not None
                         else tab[scol].astype(str).str.strip()),
        }).dropna(subset=["ticker"])
        if best is None or len(out) > len(best):
            best = out
    return best


def build(force: bool = False) -> pd.DataFrame:
    if OUT.exists() and not force:
        return pd.read_parquet(OUT)
    revids, rows = _revids(), []
    for group, title in PAGES.items():
        lo, hi = (450, 520) if group == "SP500" else (90, 115)
        for snap in SNAPSHOTS:
            key = str(snap.date())
            cache = CACHE / f"{group}_{key}.csv"
            if cache.exists():
                rows.append(pd.read_csv(cache).assign(snapshot_date=snap, group=group))
                continue
            rid = revids.get((group, key)) or _revision_at(title, snap)
            if rid is None:
                continue
            revids[(group, key)] = rid
            _save_revids(revids)
            df = _classify(_get(f"https://en.wikipedia.org/w/index.php?oldid={rid}").text,
                           lo, hi)
            if df is None or df.empty:
                print(f"  !! {group} {key}: no classified table")
                continue
            df.to_csv(cache, index=False)
            rows.append(df.assign(snapshot_date=snap, group=group))
            print(f"  {group} {key}: {len(df)} classified "
                  f"({df['industry'].nunique()} industries)")
            time.sleep(1.5)
    out = pd.concat(rows, ignore_index=True).drop_duplicates(
        subset=["snapshot_date", "ticker"])
    out.to_parquet(OUT)
    return out


if __name__ == "__main__":
    df = build(force=True)
    print(f"\nsnapshots={df['snapshot_date'].nunique()} rows={len(df)} "
          f"tickers={df['ticker'].nunique()}")
    print(f"sectors={df['sector'].nunique()} industries={df['industry'].nunique()}")
