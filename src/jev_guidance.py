"""Jev on the guidance-withdrawal interpretation task.

Evaluation 1 of Codex's three: does Jev correctly apply a defined rubric to
supplied evidence? Not "does it predict returns" -- that is a separate
question and is not asked here.

The state is the passage and nothing else. No ticker, no date, no hint of
which search found it, and no framing that asserts the answer. Questions are
frozen before any answer is seen; the cache key covers their full text, so
editing them cannot silently reuse these results.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
from typesafe_sdk import Choice, Noul, Score

import jev as J

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "jev_guidance.parquet"

QUESTIONS = {
    # The primary judgment, worded to match the rubric exactly.
    "withdrawn": Noul(instructions=(
        "Does this passage state that financial guidance the company had "
        "previously issued -- its own projections of future revenue, earnings, "
        "margin or similar -- is being withdrawn, suspended, or no longer "
        "applies? Answer no if guidance is merely reaffirmed, raised, lowered "
        "or updated, if what is withdrawn is something other than forward "
        "financial guidance, or if the language is hypothetical.")),
    # Grounding: force a choice among the populations actually present,
    # including an explicit "none of these" so agreement is not forced.
    "what_happened": Choice(
        instructions="What does this passage principally report?",
        criteria={
            "guidance_withdrawn":
                "Previously issued forward financial guidance is withdrawn or suspended",
            "guidance_still_applies":
                "Forward guidance is reaffirmed, raised, lowered or updated, and still stands",
            "financials_not_reliable":
                "Previously issued historical financial statements should no longer be relied upon",
            "something_else":
                "None of the above",
        }),
    "explicit": Score(
        instructions=(
            "How explicit is the passage about the status of previously issued "
            "forward financial guidance?"),
        criteria=["Silent on it", "Implied only", "Stated indirectly",
                  "Stated plainly", "Stated unmistakably"]),
}


def main() -> None:
    df = pd.read_parquet(ROOT / "data" / "guidance_corpus.parquet")
    rows = df.to_dict("records")
    print(f"asking Jev about {len(rows)} passages ...")
    t0 = time.time()

    def work(r):
        a = J.ask(r["passage"], QUESTIONS, "guidance_v1")
        return dict(bid=r["bid"],
                    jev_noul=a["withdrawn"]["noul"],
                    jev_choice=a["what_happened"]["choice"],
                    jev_choice_conf=a["what_happened"].get("confidence"),
                    jev_explicit=a["explicit"]["score"])

    with ThreadPoolExecutor(max_workers=8) as ex:
        out = list(ex.map(work, rows))
    J.save_cache()
    res = pd.DataFrame(out)
    res.to_parquet(OUT)
    st = J.stats()
    print(f"done in {time.time()-t0:.0f}s | {st['calls']} calls, {st['hits']} cached, "
          f"{st['input_tokens']:,} input tokens "
          f"(${st['input_tokens']/1e6*0.042:.3f})")
    print(res[["jev_noul", "jev_explicit"]].describe().round(3).to_string())
    print(res["jev_choice"].value_counts().to_string())


if __name__ == "__main__":
    main()
