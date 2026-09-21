"""Point-in-time fundamentals from SEC XBRL: the C and A of CAN SLIM.

`strategy.py` said earnings were out of reach because "point-in-time
fundamentals ... yfinance cannot supply for delisted names". True of yfinance,
false of EDGAR. Every XBRL fact carries the date it was FILED, so the value a
trader could see on day t is exactly the set of facts with filed <= t. Nothing
has to be reconstructed or assumed, and EDGAR keeps filings for companies that
no longer trade: SVB Financial's last 10-K, EPS 25.35, was filed 2023-02-24,
two weeks before the bank failed.

This is the state O'Neil's method needs and Jev was never given. A stateless
model cannot know a company's earnings for the same reason it cannot know what
day it is: nobody told it.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FACTS = RAW / "xbrl"
UA = {"User-Agent": "jev-trade-research zhisong.guo@gmail.com"}

# Diluted EPS and revenue carry C and A. Filers disagree on the revenue tag,
# so several are accepted and the first present wins.
EPS = ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"]
REV = ["RevenueFromContractWithCustomerExcludingAssessedTax",
       "RevenueFromContractWithCustomerIncludingAssessedTax",
       "Revenues", "SalesRevenueNet"]


def cik_map() -> dict[str, str]:
    p = RAW / "cik_map.json"
    if not p.exists():
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=UA, timeout=30)
        r.raise_for_status()
        p.write_text(json.dumps(
            {v["ticker"]: f"{v['cik_str']:010d}" for v in r.json().values()}))
    return json.loads(p.read_text())


def fetch(cik: str) -> dict | None:
    """companyfacts for one CIK, cached on disk. SEC asks for <=10 req/s."""
    FACTS.mkdir(parents=True, exist_ok=True)
    p = FACTS / f"{cik}.json"
    if p.exists():
        return json.loads(p.read_text()) if p.stat().st_size > 2 else None
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=30)
        except requests.RequestException:
            time.sleep(1 + attempt)
            continue
        if r.status_code == 200:
            p.write_text(r.text)
            return r.json()
        if r.status_code == 404:
            p.write_text("{}")
            return None
        time.sleep(1 + attempt)
    return None


def _facts(cf: dict, tags: list[str]) -> list[dict]:
    us = (cf or {}).get("facts", {}).get("us-gaap", {})
    for t in tags:
        if t in us:
            out = []
            for unit, rows in us[t]["units"].items():
                for x in rows:
                    if "start" in x and x.get("val") is not None:
                        out.append(dict(start=x["start"], end=x["end"],
                                        val=float(x["val"]), filed=x["filed"],
                                        form=x.get("form", ""), tag=t))
            if out:
                return out
    return []


def tidy(ticker: str, cf: dict) -> pd.DataFrame:
    """Long table of periodised facts, each stamped with its filing date."""
    rows = []
    for kind, tags in (("eps", EPS), ("rev", REV)):
        for f in _facts(cf, tags):
            s, e = pd.Timestamp(f["start"]), pd.Timestamp(f["end"])
            days = (e - s).days
            span = ("Q" if 80 <= days <= 100 else
                    "Y" if 350 <= days <= 380 else None)
            if span is None:                 #半-year and YTD spans are dropped
                continue
            rows.append(dict(ticker=ticker, kind=kind, span=span,
                             start=s, end=e, val=f["val"],
                             filed=pd.Timestamp(f["filed"]), form=f["form"]))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # One filing can restate an earlier period; keep the EARLIEST filing of
    # each period, because that is the number a trader first saw.
    return (df.sort_values("filed")
              .drop_duplicates(["ticker", "kind", "span", "end"], keep="first"))


def build(tickers: list[str]) -> pd.DataFrame:
    m = cik_map()
    parts, miss = [], []
    for i, t in enumerate(tickers, 1):
        cik = m.get(t)
        if not cik:
            miss.append(t)
            continue
        cf = fetch(cik)
        if cf:
            d = tidy(t, cf)
            if len(d):
                parts.append(d)
        if i % 50 == 0:
            print(f"  {i}/{len(tickers)} ...", flush=True)
        time.sleep(0.11)                     # SEC fair-access
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    print(f"  {out['ticker'].nunique() if len(out) else 0} tickers with facts, "
          f"{len(out):,} periodised rows; no CIK for {len(miss)}")
    if len(out):
        out.to_parquet(RAW / "fundamentals.parquet")
        (RAW / "fundamentals_missing.json").write_text(json.dumps(miss))
    return out


if __name__ == "__main__":
    import universe as U
    tk = sorted(set().union(*U.membership().values()))
    print(f"building point-in-time fundamentals for {len(tk)} tickers")
    build(tk)


# --------------------------------------------------------------------------
# What was knowable on a given day.
# --------------------------------------------------------------------------
def _yoy(rows: pd.DataFrame, span: str) -> tuple[float | None, float | None,
                                                 pd.Timestamp | None]:
    """Growth of the latest period against the same period a year earlier."""
    d = rows[rows["span"] == span].sort_values("end")
    if len(d) < 2:
        return None, None, None
    cur = d.iloc[-1]
    target = cur["end"] - pd.Timedelta(days=365)
    prior = d[(d["end"] - target).abs() <= pd.Timedelta(days=20)]
    if not len(prior):
        return None, None, cur["end"]
    p = prior.iloc[-1]["val"]
    if p == 0:
        return None, cur["val"], cur["end"]
    # A swing from a loss to a profit is not a percentage; report it as such.
    g = None if p < 0 and cur["val"] < 0 else (cur["val"] - p) / abs(p) * 100
    return g, cur["val"], cur["end"]


def pit(df: pd.DataFrame, ticker: str, asof) -> dict:
    """Earnings facts filed on or before `asof`. Nothing later is visible."""
    asof = pd.Timestamp(asof)
    d = df[(df["ticker"] == ticker) & (df["filed"] <= asof)]
    if not len(d):
        return {}
    eps, rev = d[d["kind"] == "eps"], d[d["kind"] == "rev"]
    qg, qv, qend = _yoy(eps, "Q")
    ag, av, _ = _yoy(eps, "Y")
    rg, _, _ = _yoy(rev, "Q")
    last_filed = d["filed"].max()
    return dict(
        eps_q_growth=qg, eps_q_val=qv, eps_a_growth=ag, eps_a_val=av,
        rev_q_growth=rg, quarter_end=qend, last_filed=last_filed,
        days_stale=int((asof - last_filed).days) if pd.notna(last_filed) else None)


def describe(m: dict) -> str:
    """The earnings state, in the plain terms the criteria are written in.

    Absence is stated, never defaulted: "not disclosed" is different from
    "zero growth", and a stateless model has no way to tell them apart unless
    the difference is written down.
    """
    if not m:
        return "- No SEC earnings filings were available for this company yet."
    def pct(v):
        return "not determinable" if v is None else f"{v:+.0f}%"
    out = [
        f"- Most recent reported quarter ended {m['quarter_end'].date()}, "
        f"filed {m['last_filed'].date()} ({m['days_stale']} days before today)."
        if m.get("quarter_end") is not None else
        f"- Last filing {m['last_filed'].date()}; no quarterly period parsed.",
        f"- Quarterly earnings per share versus the same quarter a year "
        f"earlier: {pct(m.get('eps_q_growth'))}. O'Neil looked for 25% or more.",
        f"- Quarterly sales versus a year earlier: {pct(m.get('rev_q_growth'))}.",
        f"- Annual earnings per share versus the prior year: "
        f"{pct(m.get('eps_a_growth'))}.",
    ]
    return "\n".join(out)
