import sys; sys.path.insert(0,'/Users/michaelguo/projects/jev-trade-cc/src')
from concurrent.futures import ThreadPoolExecutor
import exam_oneil as E, jev as J

cases = E.build()
print(f"{len(cases)} cases ({len(cases)//2} pairs, "
      f"{len(cases)//len(E.DIMS)//2} per dimension)")
def ask(c):
    a = J.decide_entry(c["row"], c["bars"])
    return dict(c, at_pivot=a["at_pivot"]["noul"], supply=a["supply"]["noul"],
                orderly=J.score_of(a, "orderly"),
                prior_advance=a["prior_advance"]["noul"])
with ThreadPoolExecutor(max_workers=8) as ex:
    res = list(ex.map(ask, cases))
J.save_cache()

FIELD = dict(volume="supply", extension="at_pivot", tightness="orderly",
             advance="prior_advance")
print(f"\n{'dimension':<12}{'judgment':<16}{'good':>7}{'bad':>7}  pairs ranked right")
print("-"*62)
for d in E.DIMS:
    f = FIELD[d]
    g = {r["k"]: r[f] for r in res if r["dim"]==d and r["arm"]=="good"}
    b = {r["k"]: r[f] for r in res if r["dim"]==d and r["arm"]=="bad"}
    ok = sum(g[k] > b[k] for k in g)
    print(f"{d:<12}{f:<16}{sum(g.values())/len(g):>7.2f}"
          f"{sum(b.values())/len(b):>7.2f}  {ok}/{len(g)}")
print()
gate = [r for r in res if r["arm"]=="bad"
        and (r["at_pivot"] < .5 or r["prior_advance"] < .5)]
bad = [r for r in res if r["arm"]=="bad"]
print(f"code gates reject {len(gate)}/{len(bad)} bad arms "
      f"({100*len(gate)/len(bad):.0f}%)")
print(f"spend ${J.stats()['input_tokens']/1e6*0.042:.3f}")

print("\n=== end-to-end entry_policy, not just the two gates ===")
raw = {(r["dim"], r["k"], r["arm"]): {
        "supply": {"noul": r["supply"]}, "at_pivot": {"noul": r["at_pivot"]},
        "prior_advance": {"noul": r["prior_advance"]},
        "orderly": {"score": r["orderly"]}} for r in res}
import statistics
print(f"{'dimension':<12}{'good arm buys':>15}{'bad arm buys':>14}"
      f"{'conviction good':>17}{'bad':>8}")
print("-"*66)
tot_g = tot_b = 0
for d in E.DIMS:
    g = [J.entry_policy(raw[(d,k,'good')]) for k in range(12)]
    b = [J.entry_policy(raw[(d,k,'bad')]) for k in range(12)]
    ng = sum(x[0]=="buy" for x in g); nb = sum(x[0]=="buy" for x in b)
    tot_g += ng; tot_b += nb
    cg = statistics.mean(x[1] for x in g if x[0]=="buy") if ng else float('nan')
    cb = statistics.mean(x[1] for x in b if x[0]=="buy") if nb else float('nan')
    print(f"{d:<12}{ng:>12}/12{nb:>11}/12{cg:>17.3f}{cb:>8.3f}")
print("-"*66)
print(f"{'TOTAL':<12}{tot_g:>12}/48{tot_b:>11}/48")
print(f"\npolicy rejects {48-tot_b}/48 bad arms ({100*(48-tot_b)/48:.0f}%), "
      f"admits {tot_g}/48 good arms ({100*tot_g/48:.0f}%)")
