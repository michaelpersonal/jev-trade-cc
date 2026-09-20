"""Point-in-time index membership, reconstructed from Wikipedia page revisions.

For each quarter-end in the backtest window we fetch the revision of the
constituent-list page as it stood on that date and parse the table. A snapshot
therefore reflects what the list said *then* -- names that were later deleted
from the page (acquired, delisted, demoted) are still present in the old
revisions, which is exactly what kills survivorship bias.

Output: data/raw/universe_pit.parquet  [snapshot_date, ticker, group]
"""
from __future__ import annotations

import re
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
OUT = RAW / "universe_pit.parquet"

API = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "jev-trade-backtest/0.1 (personal research)"}

PAGES = {"SP500": "List of S&P 500 companies", "ND100": "Nasdaq-100"}

# Quarterly snapshots. The first predates the backtest start so day one has a
# universe; the last is today.
SNAPSHOTS = (
    pd.date_range("2021-12-31", "2026-09-20", freq="QE").tolist()
    + [pd.Timestamp("2026-09-20")]
)


def _get(url: str, **kw) -> requests.Response:
    """GET with backoff. Wikipedia answers 429 when we push it, so back off hard."""
    for attempt in range(6):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            if r.status_code == 429:
                raise requests.HTTPError("429", response=r)
            r.raise_for_status()
            return r
        except Exception:
            if attempt == 5:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def _revision_at(title: str, when: pd.Timestamp) -> int | None:
    """id of the last revision of `title` at or before `when`."""
    r = _get(API, params={
        "action": "query", "prop": "revisions", "titles": title, "rvlimit": 1,
        "rvstart": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "rvdir": "older",
        "rvprop": "ids|timestamp", "format": "json",
    }).json()
    page = next(iter(r["query"]["pages"].values()))
    revs = page.get("revisions")
    return revs[0]["revid"] if revs else None


def _clean(sym: object) -> str | None:
    """Wikipedia writes BRK.B; yfinance wants BRK-B."""
    s = str(sym).strip().upper().replace(".", "-")
    s = re.sub(r"\[.*?\]", "", s).strip()
    return s if re.fullmatch(r"[A-Z][A-Z\-]{0,6}", s) else None


def _constituents(html: str, expect: tuple[int, int]) -> list[str]:
    """Pick the table that looks like a constituent list and read its tickers."""
    lo, hi = expect
    best: list[str] = []
    for tab in pd.read_html(StringIO(html)):
        if not (lo <= len(tab) <= hi):
            continue
        cols = {str(c).split("'")[1] if isinstance(c, tuple) else str(c): c
                for c in tab.columns}
        for name, col in cols.items():
            if name.strip().lower() in ("symbol", "ticker"):
                syms = [c for c in (_clean(v) for v in tab[col]) if c]
                if len(syms) > len(best):
                    best = syms
    return best


def build(force: bool = False) -> pd.DataFrame:
    if OUT.exists() and not force:
        return pd.read_parquet(OUT)
    snapdir = RAW / "snapshots"
    snapdir.mkdir(exist_ok=True)
    rows = []
    for group, title in PAGES.items():
        expect = (450, 520) if group == "SP500" else (90, 115)
        for snap in SNAPSHOTS:
            cache = snapdir / f"{group}_{snap.date()}.csv"
            if cache.exists():
                syms = cache.read_text().split()
            else:
                rid = _revision_at(title, snap)
                if rid is None:
                    continue
                html = _get(f"https://en.wikipedia.org/w/index.php?oldid={rid}").text
                syms = sorted(set(_constituents(html, expect)))
                if not syms:
                    print(f"  !! {group} {snap.date()} rev {rid}: no table matched")
                    continue
                cache.write_text("\n".join(syms))
                print(f"  {group} {snap.date()}: {len(syms)} names (rev {rid})")
                time.sleep(1.5)  # be polite to Wikipedia
            rows += [{"snapshot_date": snap, "ticker": t, "group": group}
                     for t in syms]
    df = pd.DataFrame(rows)
    df.to_parquet(OUT)
    return df


def membership() -> dict[pd.Timestamp, set[str]]:
    """{snapshot_date: set of tickers in either index on that date}."""
    df = build()
    return {d: set(g["ticker"]) for d, g in df.groupby("snapshot_date")}


def members_on(date: pd.Timestamp, memb: dict[pd.Timestamp, set[str]]) -> set[str]:
    """Universe visible on `date`: the most recent snapshot at or before it."""
    usable = [d for d in memb if d <= date]
    return memb[max(usable)] if usable else set()


if __name__ == "__main__":
    df = build(force=True)
    print("\nsnapshots:", df["snapshot_date"].nunique(),
          "| rows:", len(df), "| distinct tickers:", df["ticker"].nunique())
