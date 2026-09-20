"""Build a point-in-time corpus of SEC filing passages about forward guidance.

The research question is an INTERPRETATION task, not a forecast: given a short
passage from an original filing, does it explicitly state that previously
issued financial guidance no longer applies?

Point-in-time discipline:
  * Documents are fetched from the original accession, never a later amendment.
  * `acceptanceDateTime` from the submissions API is the moment the filing
    became public. That, not the fiscal period or the filing date, is when a
    trader could first have read it.
  * A current XBRL value for an old fiscal period is NOT point-in-time data and
    is not used anywhere here.

The corpus deliberately mixes three populations so the task is not trivial:
  withdrawal     explicit withdrawal or suspension of guidance
  guidance_move  reaffirm / raise / lower / narrow / update -- guidance is
                 discussed and changed, but it still applies
  non_reliance   "previously issued financial statements should no longer be
                 relied upon" -- a withdrawal of something, but of past
                 financials rather than forward guidance. The sharpest
                 distractor in the set.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "edgar"
RAW.mkdir(parents=True, exist_ok=True)

# SEC asks that automated traffic declare itself. No personal address is used.
UA = {"User-Agent": "Jev Trade Research research@jev-trade.example.com",
      "Accept-Encoding": "gzip, deflate"}
FTS = "https://efts.sec.gov/LATEST/search-index"
START, END = "2022-01-01", "2026-09-18"

QUERIES = {
    "withdrawal": ['"withdrawing its guidance"', '"withdrawing our guidance"',
                   '"withdraws its guidance"', '"withdrawing its full-year"',
                   '"suspending its guidance"', '"withdrawing previously issued"',
                   '"is not reaffirming"', '"withdrawing its prior"',
                   '"withdrew its guidance"', '"suspends its guidance"'],
    "guidance_move": ['"reaffirming its full-year"', '"raising its full-year"',
                      '"lowering its full-year"', '"narrowing its full-year"',
                      '"reiterated its full-year"'],
    "non_reliance": ['"no longer be relied upon"'],
}
CAP = {"withdrawal": 400, "guidance_move": 30, "non_reliance": 40}


def _get(url, **kw):
    for attempt in range(4):
        r = requests.get(url, headers=UA, timeout=40, **kw)
        if r.status_code == 200:
            return r
        time.sleep(1.5 * (attempt + 1))
    r.raise_for_status()
    return r


def search(query: str, cap: int) -> list[dict]:
    """Full-text search hits, paged. Returns accession + document id."""
    out, frm = [], 0
    while len(out) < cap:
        r = _get(FTS, params={"q": query, "forms": "8-K", "dateRange": "custom",
                              "startdt": START, "enddt": END, "from": frm})
        hits = r.json().get("hits", {}).get("hits", [])
        if not hits:
            break
        for h in hits:
            adsh, _, doc = h["_id"].partition(":")
            src = h["_source"]
            names = src.get("display_names") or [""]
            cik = re.search(r"CIK (\d{10})", names[0])
            out.append(dict(adsh=adsh, doc=doc, form=src.get("form"),
                            file_date=src.get("file_date"),
                            company=names[0].split("  (")[0],
                            cik=cik.group(1) if cik else None, query=query))
        frm += len(hits)
        time.sleep(0.4)
    return out[:cap]


def acceptance(cik: str, adsh: str) -> str | None:
    """When the filing actually became public."""
    cache = RAW / f"sub_{cik}.json"
    if cache.exists():
        d = json.loads(cache.read_text())
    else:
        d = _get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
        cache.write_text(json.dumps(d))
        time.sleep(0.3)
    rec = d.get("filings", {}).get("recent", {})
    for i, a in enumerate(rec.get("accessionNumber", [])):
        if a == adsh:
            return rec.get("acceptanceDateTime", [None] * (i + 1))[i]
    return None


TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"[ \t\xa0]+")


def document_text(cik: str, adsh: str, doc: str) -> str:
    cache = RAW / f"doc_{adsh}_{doc}.txt"
    if cache.exists():
        return cache.read_text()
    url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
           f"{adsh.replace('-', '')}/{doc}")
    html = _get(url).text
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    txt = TAG.sub(" ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#8217;", "'"),
                 ("&#8220;", '"'), ("&#8221;", '"'), ("&#151;", "-"),
                 ("&#146;", "'"), ("&rsquo;", "'"), ("&ldquo;", '"'),
                 ("&rdquo;", '"'), ("&#8212;", "-")):
        txt = txt.replace(a, b)
    txt = WS.sub(" ", txt)
    txt = re.sub(r"\s*\n\s*", "\n", txt).strip()
    cache.write_text(txt)
    time.sleep(0.3)
    return txt


def passage(text: str, phrase: str, before: int = 700, after: int = 900) -> str | None:
    """A window around the first occurrence of the matched phrase."""
    core = phrase.strip('"').lower()
    i = text.lower().find(core)
    if i < 0:
        words = core.split()
        i = text.lower().find(" ".join(words[:2])) if len(words) > 1 else -1
        if i < 0:
            return None
    lo, hi = max(0, i - before), min(len(text), i + len(core) + after)
    seg = text[lo:hi]
    seg = seg[seg.find(" ") + 1:]                       # avoid a half word
    return re.sub(r"\n{2,}", "\n", seg).strip()
