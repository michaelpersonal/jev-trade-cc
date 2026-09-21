# The universe has a hole in it, and it is bigger than every effect we measured

## The gap

The point-in-time universe has 635 names that were S&P 500 members at some
point between 2022-01-03 and 2026-09-18. The price panel has 586. **49 members
(7.7%) have no price data at all.**

```
SIVB  FRC   ATVI  PXD   HES   SGEN  ABMD  CERN  TWTR  CTXS  DISCA DISCK
XLNX  ANSS  SPLK  JNPR  CTLT  VIAC  NLSN  WLTW  ANTM  PKI   DRE   FBHS
BLL   RE    PEAK  CDAY  DAY   FI    FLT   NLOK  ABC   BK    CMA   DFS
DISH  GPS   HOLX  IPG   K     MMC   MRO   NLOK  PBCT  SATS  SEE   WBA   WRK
```

These are not a random 49. They are the names that stopped trading: failures
(SIVB, FRC), acquisitions (ATVI, PXD, SGEN, XLNX, ANSS, SPLK, JNPR, DFS, MRO,
WRK, K, IPG, CMA, HOLX), take-privates (TWTR, CTXS, WBA), and mergers
(DISCA/DISCK/VIAC). yfinance does not serve delisted tickers, so the provider
silently returns the survivors. `data.py` printed the list once and continued.
It was never acted on, and every published number in this project rests on it.

No fix is available here. Yahoo will not serve these names, Stooq is behind a
bot challenge, and no other provider is configured. **The gap is permanent
until a data source that retains delisted securities is added.**

What is fixable is pretending it does not matter.

## How big is it

The hole cannot be filled, but a hole of the same size and shape can be
punched deliberately. Drop another 49 tickers, rebuild the signals, re-run the
rules-only shipped configuration, repeat 20 times. Scheme A drops uniformly.
Scheme B drops names that actually left the index in-window, which is the same
selection process that produced the real gap.

| | min | median | max | sd | spread |
|---|---|---|---|---|---|
| A, uniform | $111,844 | $171,961 | $217,424 | $22,999 | **$105,580** |
| B, left the index | $175,854 | $194,303 | $211,043 | $15,296 | $35,189 |

Full panel, for reference: **$170,234**.

Two things follow.

**The result has error bars of roughly +/-$45,000 from universe composition
alone.** A concentrated book — 5 slots, 116 buys in 4.7 years — is decided by
whether it happens to catch a handful of large winners. Which names are in the
universe determines that. Reporting a six-figure result to the dollar implies
a precision the method does not have.

**The direction of the real bias is probably favourable to the strategy.**
Under scheme B, removing names that left the index *improves* the median
result by 14.1%. The real 49 left the index and are already removed. Their
absence is likely flattering every number here.

## Effect sizes, in order

| effect | magnitude |
|---|---|
| universe composition, 7.7% hole | **$105,580** spread, sd $22,999 |
| prompt wording (semantically equivalent variants) | $45,752 spread |
| Jev entry+exit vs rules only | $11,221 |
| interest never earned on 31.5% average cash | $9,243 |

The quantity this project set out to measure is the third row. It is smaller
than the measurement noise in the first, and smaller than the prose
sensitivity in the second. **No conclusion about whether Jev can trade stocks
is supportable from a single run of this backtest**, in either direction.

That is not a statement about Jev. It is a statement about the experiment.

## What would make it answerable

- A data source that retains delisted securities, so the universe is whole.
- Interest on idle cash, so the cash-heavy arm is not handicapped against a
  fully-invested benchmark.
- Many runs, not one: report a distribution over universe draws and over
  pre-registered prompt paraphrases, and compare arms within draw.
- More positions or more trades, so a single name matters less. With 5 slots
  and 22 buys a year, individual luck dominates.
