"""The carried contract: what was concluded about a setup, and where its base was.

Every stage of this system used to re-derive its facts from the rolling signal
table instead of receiving them from the stage before, and so every boundary
could silently disagree with the last:

  * Phase A asked Jev which O'Neil pattern a chart was and where its buy point
    sat. Phase B threw the answer away and recomputed a 65-session rolling high,
    presenting it to Jev as "the base".
  * The base a position actually broke out of was never stored. The exit prompt
    recomputed today's rolling pivot and called it "the top of the base it broke
    out of". That reference climbs with the stock: ten sessions after one real
    breakout the position was +0.1% above its true base while the prompt said
    -3.3% below it. The sign was wrong, not just the magnitude.

An Anchor is created once, when a candidate is judged, and is then carried --
never recomputed. Code may measure distances and durations FROM an anchor; it
may not invent a new one later.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

import pandas as pd


@dataclass(frozen=True)
class Anchor:
    ticker: str
    decided_on: pd.Timestamp        # the session whose close produced this
    source: str                     # "screen" | "jev_select" | "nearmiss"

    # The base as measured on decided_on, frozen. base_top is the level the
    # breakout cleared; it is NOT recomputed later under any circumstances.
    base_top: float
    base_depth: float
    base_len_wk: float

    # What Jev concluded, when Jev was consulted. Empty for mechanical arms.
    pattern: str | None = None      # Jev's pattern identification
    setup: str | None = None        # valid / developing / extended / faulty ...
    supply: float | None = None
    prior_advance: float | None = None
    prompt_fp: str | None = None    # fingerprint of the criteria that judged it

    def distance_pct(self, price: float) -> float:
        """Where `price` sits relative to THIS base's top, in percent."""
        return (price / self.base_top - 1.0) * 100.0

    def as_record(self) -> dict:
        d = asdict(self)
        d["decided_on"] = str(pd.Timestamp(self.decided_on).date())
        return d


def from_row(row, ticker: str, decided_on, source: str,
             assessment: dict | None = None, prompt_fp: str | None = None
             ) -> Anchor:
    """Build the anchor from the signal row that justified the decision."""
    a = assessment or {}
    return Anchor(
        ticker=ticker, decided_on=pd.Timestamp(decided_on), source=source,
        base_top=float(row["pivot"]),
        base_depth=float(row["base_depth"]),
        base_len_wk=float(row["base_len_wk"]),
        pattern=a.get("pattern"), setup=a.get("setup"),
        supply=a.get("supply"), prior_advance=a.get("prior_advance"),
        prompt_fp=prompt_fp)
