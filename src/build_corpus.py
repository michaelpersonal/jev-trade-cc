"""Assemble the guidance-language corpus. No Jev, no labels -- evidence only."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd

import edgar as E

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "guidance_corpus.parquet"


def main() -> None:
    rows, seen = [], set()
    for population, queries in E.QUERIES.items():
        cap = E.CAP[population]
        got = 0
        for q in queries:
            if got >= cap:
                break
            try:
                hits = E.search(q, cap - got)
            except Exception as exc:
                print(f"  search failed {q}: {exc}")
                continue
            for h in hits:
                if not h["cik"] or h["adsh"] in seen:
                    continue
                try:
                    txt = E.document_text(h["cik"], h["adsh"], h["doc"])
                    seg = E.passage(txt, h["query"])
                    if not seg or len(seg) < 200:
                        continue
                    acc = E.acceptance(h["cik"], h["adsh"])
                except Exception as exc:
                    print(f"  fetch failed {h['adsh']}: {type(exc).__name__}")
                    continue
                seen.add(h["adsh"])
                rows.append(dict(
                    doc_id=f"{h['adsh']}:{h['doc']}", adsh=h["adsh"], cik=h["cik"],
                    company=h["company"], form=h["form"], file_date=h["file_date"],
                    acceptance=acc, population=population, query=h["query"],
                    passage=seg))
                got += 1
                if got >= cap:
                    break
            print(f"  {population:14s} {q:34s} running total {got}", flush=True)
            time.sleep(0.3)
    df = pd.DataFrame(rows)
    df.to_parquet(OUT)
    print(f"\ncorpus: {len(df)} passages, {df['cik'].nunique()} issuers")
    print(df["population"].value_counts().to_string())
    print(f"date range {df['file_date'].min()} .. {df['file_date'].max()}")
    print(f"passage length: median {int(df.passage.str.len().median())} chars")
    print(f"acceptance timestamps present: {df['acceptance'].notna().sum()}/{len(df)}")


if __name__ == "__main__":
    main()
