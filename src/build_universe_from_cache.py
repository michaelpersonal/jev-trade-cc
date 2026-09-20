"""Assemble universe_pit.parquet from whatever snapshot CSVs are on disk.

The Wikipedia fetch is rate-limited and may die partway; the per-snapshot CSVs
it already wrote are still good, so the panel can be built from those. Any
missing snapshot just means `members_on` carries the previous one forward,
which is the correct fallback -- membership changes slowly.
"""
from pathlib import Path
import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

rows = []
for f in sorted((RAW / "snapshots").glob("*.csv")):
    group, date = f.stem.split("_", 1)
    for t in f.read_text().split():
        rows.append({"snapshot_date": pd.Timestamp(date), "ticker": t, "group": group})

df = pd.DataFrame(rows).drop_duplicates(subset=["snapshot_date", "ticker"])
df.to_parquet(RAW / "universe_pit.parquet")
n = df.groupby("snapshot_date")["ticker"].nunique()
print(f"snapshots={df['snapshot_date'].nunique()} rows={len(df)} "
      f"distinct_tickers={df['ticker'].nunique()}")
print(f"universe size per snapshot: min={n.min()} max={n.max()}")
print(f"coverage {n.index.min().date()} -> {n.index.max().date()}")
