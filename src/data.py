"""Daily price panel for every ticker that was ever in the PIT universe.

`Close` from yfinance is already split-adjusted but NOT dividend-adjusted, so
it is the right series to trade on: ratios (moving averages, 52w highs,
breakout pivots) are unaffected by splits, and the level still matches what a
trader saw.

Dividends are NOT modelled -- held positions earn price return only. The
benchmark is ^GSPC, which is likewise a price index, so neither side of the
comparison collects dividends. The residual bias slightly FAVOURS the strategy:
buy-and-hold forgoes a full yield on 100% exposure while the strategy forgoes
it on roughly 55%.

Output: data/raw/panel.parquet  (long: date, ticker, open/high/low/close/volume)
        data/raw/index__GSPC.parquet
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# 2020-09-01 gives >15 months of history before the 2022-01-03 start, enough
# for a 200-day MA and a 52-week high on day one.
START = "2020-09-01"
END = "2026-09-19"          # yfinance end is exclusive; last bar = 2026-09-18
CHUNK = 250


def _chunks(xs: list[str], n: int) -> list[list[str]]:
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def _tidy(raw: pd.DataFrame) -> pd.DataFrame:
    """yfinance wide multiindex -> long [date,ticker,open,high,low,close,volume]."""
    if isinstance(raw.columns, pd.MultiIndex):
        try:
            df = raw.stack(level=1, future_stack=True).reset_index()
        except TypeError:
            df = raw.stack(level=1).reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        df = df.rename(columns={df.columns[0]: "date", df.columns[1]: "ticker"})
    else:
        return pd.DataFrame()
    keep = ["date", "ticker", "open", "high", "low", "close", "volume"]
    df = df[[c for c in keep if c in df.columns]]
    return df.dropna(subset=["close"])


def panel(tickers: list[str], force: bool = False) -> pd.DataFrame:
    out = RAW / "panel.parquet"
    if out.exists() and not force:
        return pd.read_parquet(out)
    tickers = sorted(set(tickers))
    parts = []
    for i, chunk in enumerate(_chunks(tickers, CHUNK)):
        key = hashlib.md5(",".join(chunk).encode()).hexdigest()[:12]
        cache = RAW / f"px_{key}.parquet"
        if cache.exists():
            parts.append(pd.read_parquet(cache))
            print(f"  chunk {i}: cached")
            continue
        for attempt in range(3):
            raw = yf.download(chunk, start=START, end=END, progress=False,
                              auto_adjust=False, group_by="column", threads=True)
            if not raw.empty:
                break
            time.sleep(3 * (attempt + 1))
        tidy = _tidy(raw)
        tidy.to_parquet(cache)
        parts.append(tidy)
        print(f"  chunk {i}: {tidy['ticker'].nunique()}/{len(chunk)} tickers, "
              f"{len(tidy):,} rows")
    df = pd.concat(parts, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    df.to_parquet(out)
    return df


def index_prices(ticker: str = "^GSPC", force: bool = False) -> pd.DataFrame:
    out = RAW / "index__GSPC.parquet"
    if out.exists() and not force:
        d = pd.read_parquet(out)
        d.index = pd.to_datetime(d.index)
        return d
    d = yf.download(ticker, start=START, end=END, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = [c[0] for c in d.columns]
    d.index.name = "Date"
    d.to_parquet(out)
    return d


if __name__ == "__main__":
    import universe
    u = universe.build()
    tickers = sorted(u["ticker"].unique())
    print(f"PIT universe: {len(tickers)} distinct tickers ever a member")
    df = panel(tickers)
    got = set(df["ticker"].unique())
    missing = sorted(set(tickers) - got)
    print(f"panel: {len(got)} tickers, {len(df):,} rows, "
          f"{df['date'].min().date()} -> {df['date'].max().date()}")
    # This gap is survivorship bias, not a nuisance. yfinance does not serve
    # tickers that stopped trading, so the names it silently omits are exactly
    # the ones that were acquired, taken private or failed -- the outcomes a
    # momentum backtest most needs to see. Printing it once and continuing is
    # how it survived unnoticed through every result this project published.
    # Write it down where the pipeline can read it, and say how bad it is.
    frac = len(missing) / len(tickers)
    (RAW / "panel_missing.json").write_text(json.dumps(
        {"universe": len(tickers), "fetched": len(got),
         "missing": missing, "missing_frac": round(frac, 4)}, indent=2))
    print(f"no data for {len(missing)} ({frac:.1%}): {missing}")
    if frac > 0.02:
        print(f"\n*** SURVIVORSHIP GAP: {frac:.1%} of the point-in-time "
              f"universe has no price data. ***\n*** These names cannot be "
              f"bought and are absent from the RS ranking population. Any "
              f"result\n*** built on this panel is biased by their absence. "
              f"See SURVIVORSHIP.md.\n")
    idx = index_prices()
    print(f"SPX: {len(idx)} bars -> {idx.index.max().date()}")
