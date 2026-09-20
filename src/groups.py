"""Industry-group relative strength.

O'Neil's claim was that roughly half of a stock's move is its industry group's
move, which is why IBD ranks 197 groups and tells you to buy the leaders of
leading groups. This is the honest form of "trade the hot theme": the groups
are ranked by their own members' price action as of that date, so if semis are
leading in 2023 the data says so without anyone naming semis in advance.

GICS sub-industry is the group where it has enough members that day to give a
stable reading; otherwise the coarser GICS sector stands in.
"""
from __future__ import annotations

import pandas as pd

MIN_MEMBERS = 4        # below this a sub-industry median is noise


def attach(sig: pd.DataFrame, sec: pd.DataFrame) -> pd.DataFrame:
    """Add sector/industry as they stood on each row's date."""
    snaps = sorted(pd.to_datetime(sec["snapshot_date"].unique()))
    sig = sig.sort_values("date")
    parts = []
    for i, snap in enumerate(snaps):
        lo = pd.Timestamp.min if i == 0 else snap          # first snapshot also
        hi = snaps[i + 1] if i + 1 < len(snaps) else pd.Timestamp.max  # covers before
        m = (sig["date"] >= lo) & (sig["date"] < hi)
        if not m.any():
            continue
        cls = sec.loc[sec["snapshot_date"] == snap, ["ticker", "sector", "industry"]]
        parts.append(sig[m].merge(cls.drop_duplicates("ticker"), on="ticker", how="left"))
    return pd.concat(parts, ignore_index=True)


def rank(sig: pd.DataFrame) -> pd.DataFrame:
    """Add `group` and `group_pct` (0-1 rank of the group that day)."""
    sig = sig.copy()
    sig["industry"] = sig["industry"].fillna(sig["sector"])
    n = sig.groupby(["date", "industry"])["rs_score"].transform("size")
    sig["group"] = sig["industry"].where(n >= MIN_MEMBERS, sig["sector"])

    # A group's strength is the median RS of its members that day -- median so
    # one runaway name cannot drag a weak group into the leaders.
    med = sig.groupby(["date", "group"])["rs_score"].transform("median")
    sig["group_rs"] = med
    sig["group_pct"] = sig.groupby("date")["group_rs"].rank(pct=True)
    return sig
