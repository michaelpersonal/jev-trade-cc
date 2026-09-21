"""How much does a 7.7% hole in the universe move the result?

The real gap cannot be filled: yfinance does not serve delisted tickers and
no other provider is configured here. What can be measured is the SIZE of a
hole that shape. Punch another one of the same size in the panel and re-run.

Scheme A drops 49 tickers uniformly. Scheme B drops 49 that actually left the
index during the window -- the same selection process that produced the real
gap, so it is the closer analogue.
"""
import sys, random, pandas as pd, numpy as np
sys.path.insert(0,'/Users/michaelguo/projects/jev-trade-cc/src')
import strategy as S, universe as U, backtest as B, data as D, compare as C

pan = pd.read_parquet('../data/raw/panel.parquet')
memb = U.membership()
idx = D.index_prices()
have = set(pan['ticker'].unique())

snaps = sorted(memb)
inwin = [s for s in snaps if pd.Timestamp('2022-01-03') <= s <= pd.Timestamp('2026-09-18')]
first, last = memb[inwin[0]], memb[inwin[-1]]
left = sorted((first - last) & have)          # were members, then were not
print(f"tickers that left the index in-window and we DO have: {len(left)}")

def run_with(drop):
    p = pan[~pan['ticker'].isin(drop)]
    sig = S.build_signals(p, membership=memb)
    C.apply_shipped()
    S.JEV_ENTRY = S.JEV_EXIT = False; S.JEV_SELECT = False; S.NEARMISS_MODE = 3
    B.load_panel(p)
    r = B.run(sig, idx, memb)
    buy = int(sig[(sig['date']>='2022-01-03')&(sig['date']<='2026-09-18')]
              ['buyable'].fillna(False).sum())
    return r['equity'][-1], buy

base, base_buy = run_with(set())
print(f"\nfull panel (still missing the real 49): ${base:,.0f}, "
      f"{base_buy} buyable rows\n")

rng = random.Random(0)
for name, pool in (("A uniform", sorted(have)), ("B left the index", left)):
    res = []
    for k in range(20):
        drop = set(rng.sample(pool, min(49, len(pool))))
        eq, bu = run_with(drop)
        res.append((eq, bu))
    eqs = np.array([x[0] for x in res]); bus = np.array([x[1] for x in res])
    print(f"{name}: 20 draws, 49 more tickers removed")
    print(f"   final equity  min ${eqs.min():>9,.0f}   median ${np.median(eqs):>9,.0f}"
          f"   max ${eqs.max():>9,.0f}")
    print(f"   vs full panel {100*(eqs.min()/base-1):>+7.1f}%"
          f"        {100*(np.median(eqs)/base-1):>+7.1f}%"
          f"         {100*(eqs.max()/base-1):>+7.1f}%")
    print(f"   mean ${eqs.mean():,.0f}  sd ${eqs.std(ddof=1):,.0f}"
          f"  spread ${eqs.max()-eqs.min():,.0f}")
    print(f"   buyable rows {bus.min()}-{bus.max()} (full {base_buy})")
    print(f"   a single run's 95% interval on universe choice alone: "
          f"+/-${1.96*eqs.std(ddof=1):,.0f}\n")
