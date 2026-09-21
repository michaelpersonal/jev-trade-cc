"""Conformance exam for the prompts that actually decide trades.

The previous runner called ENTRY_DECISION, which the selection configuration
does not use. It therefore could not say anything about whether the current
selector understands O'Neil. This exercises ASSESS -- the question set that
produces every assessment the selector reads -- and the selection call itself,
on fixtures whose invariants are asserted rather than assumed.
"""
from __future__ import annotations

import json
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import anchor as A
import exam_oneil as E
import jev as J

FIELD = {"volume": "supply", "advance": "prior_advance"}


def main() -> None:
    cases = E.build()
    print(f"{len(cases)} cases, {len(cases)//2} pairs, "
          f"ASSESS fingerprint {J.question_fingerprint(J.ASSESS, 'assess')}\n")

    # assert the fixture invariants before spending anything on them
    for c in cases:
        piv, bars = c["row"]["pivot"], c["bars"]
        assert abs(piv - bars["high"].iloc[:-1].max()) < 1e-9, "pivot not derived"
        if c["arm"] == "good":
            assert c["row"]["close"] > piv, "good arm does not clear its pivot"
    print("fixture invariants hold: pivot derived from the bars, good arms "
          "clear it\n")

    def ask(c):
        a = J.assess(c["row"], c["bars"])
        return dict(c,
                    setup=J.choice_of(a, "setup", set(J.ASSESS["setup"].criteria)),
                    pattern=J.choice_of(a, "pattern", set(J.ASSESS["pattern"].criteria)),
                    pattern_conf=a["pattern"].get("confidence"),
                    setup_conf=a["setup"].get("confidence"),
                    supply=a["supply"]["noul"],
                    prior_advance=a["prior_advance"]["noul"])

    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(ask, cases))
    J.save_cache()

    print("directional judgments (the two Nouls ASSESS actually asks):")
    print(f"  {'dimension':<12}{'judgment':<16}{'good':>7}{'bad':>7}{'pairs right':>13}")
    for d, f in FIELD.items():
        g = {r["k"]: r[f] for r in res if r["dim"] == d and r["arm"] == "good"}
        b = {r["k"]: r[f] for r in res if r["dim"] == d and r["arm"] == "bad"}
        ok = sum(g[k] > b[k] for k in g)
        print(f"  {d:<12}{f:<16}{statistics.mean(g.values()):>7.2f}"
              f"{statistics.mean(b.values()):>7.2f}{ok:>9}/{len(g)}")

    print("\nsetup label, by dimension and arm:")
    df = pd.DataFrame(res)
    print("  " + pd.crosstab([df["dim"], df["arm"]], df["setup"])
          .to_string().replace("\n", "\n  "))

    print("\nthe extension pair is the one ASSESS has an explicit label for:")
    e = df[df["dim"] == "extension"]
    for arm in ("good", "bad"):
        v = e[e["arm"] == arm]["setup"].value_counts().to_dict()
        print(f"  {arm:<5} {v}")

    print(f"\npattern identification: mean confidence "
          f"{df['pattern_conf'].mean():.2f} over "
          f"{len(J.ASSESS['pattern'].criteria)} options "
          f"(uniform would be {1/len(J.ASSESS['pattern'].criteria):.2f})")
    print("  " + df["pattern"].value_counts().to_string().replace("\n", "\n  "))

    # --- the selection call, on the same fixtures -------------------------
    print("\nselection: one sound in-zone base against one extended one")
    wins = 0
    for k in range(12):
        good, _ = E.case("extension", "good", 1000 + k)
        gr = E.case("extension", "good", 1000 + k)[1]
        br = E.case("extension", "bad", 1000 + k)[1]
        opts, key = {}, {}
        for lbl, r in (("A", gr), ("B", br)):
            anc = A.from_row(r, "X", pd.Timestamp("2024-01-02"), "jev_select",
                             {"pattern": "cup", "pattern_conf": 0.5})
            key[lbl] = "sound" if r is gr else "extended"
            opts[lbl] = (f"{anc.pattern_phrase()}, {anc.base_len_wk:.0f} weeks "
                         f"long and {anc.base_depth*100:.0f}% deep; close is "
                         f"{anc.distance_pct(r['close']):+.1f}% from its buy "
                         f"point; relative strength 88 of 99")
        state = "\n".join(f"Option {a}: {b}" for a, b in opts.items())
        pick = J.choice_of(J.ask(state, J.select_question(opts), "select_v1"),
                           "pick", set(opts) | {"none"})
        wins += key.get(pick, "none") == "sound"
    J.save_cache()
    print(f"  chose the in-zone base over the extended one: {wins}/12")
    print(f"\nspend ${J.stats()['input_tokens']/1e6*0.042:.3f}")


if __name__ == "__main__":
    main()
