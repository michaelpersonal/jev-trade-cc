# The universe has a hole in it

## The gap

The point-in-time universe holds 635 names that were S&P 500 members at some
point between 2022-01-03 and 2026-09-18. The price panel holds 586. **49
members (7.7%) have no price data.** yfinance does not serve tickers that have
stopped trading, so the omission is systematic rather than random, and
`data.py` printed the list once and continued. Every published number in this
project rests on that panel.

`data.py` now writes `data/raw/panel_missing.json` and refuses to pass the gap
in silence. The gap itself cannot be closed here: Yahoo will not serve these
names, Stooq is behind a bot challenge, and no other provider is configured.

### Not all 49 are irrecoverable

An earlier version of this file called all 49 delistings. That was wrong.
**Twelve are symbol changes whose successor is present in the panel**, so the
company's later history is in the data under a different identifier:

| gone | successor | | gone | successor |
|---|---|---|---|---|
| ABC | COR | | NLOK | GEN |
| ANTM | ELV | | PEAK | DOC |
| BLL | BALL | | PKI | RVTY |
| DISCA | WBD | | RE | EG |
| DISCK | WBD | | VIAC | PARA |
| FLT | CPAY | | WLTW | WTW |

The remaining 37 have no successor in the panel and include genuine failures
(SIVB, FRC), acquisitions (ATVI, PXD, SGEN, XLNX, SPLK, JNPR, DFS, MRO, WRK,
K, IPG, CMA, HOLX, ANSS, CTLT, CERN, ABMD) and take-privates (TWTR, CTXS,
WBA). Security identity should be audited before any of these is called
irrecoverable; a symbol change is a data-joining problem, not a lost history.

## What the deletion experiment does and does not show

The hole cannot be filled, but one the same size can be punched deliberately:
drop 49 tickers, rebuild the signals, re-run, repeat. `src/jackknife.py` does
this over 12 draws.

**This measures sensitivity to a deletion procedure. It does not estimate the
survivorship bias.** Removing observed survivors is not sampling the unknown
missing-data mechanism; the deleted names are not interchangeable with the
absent ones. An earlier version of this file multiplied the resulting standard
deviation by 1.96 and called it a confidence interval on that bias. **That
interpretation is withdrawn.** It also compared a single arm's dispersion
against Jev's incremental effect to conclude the effect was smaller than its
own measurement noise. **That comparison is withdrawn too** — the two are
different quantities, and the paired statistic below is the relevant one.

## The paired result

Both arms are run on the *same* deleted panel and differenced within the draw,
so shocks common to both can cancel.

| | mean | sd | min | max |
|---|---|---|---|---|
| rules-only equity | $182,966 | $17,952 | $159,317 | $217,424 |
| Jev entry+exit equity | $159,650 | $17,429 | $125,318 | $191,839 |
| **paired difference** | **−$23,315** | **$17,928** | −$61,720 | +$6,876 |

Jev trailed the mechanical rules in **11 of 12 draws**. Under a sign test that
direction is unlikely to be chance (p ≈ 0.006), though the magnitude stays
uncertain: the paired standard deviation is $17,928, essentially unreduced
from each arm's own $17,952. The common shock did **not** cancel, which is
worth stating because I expected it to.

What this supports: under this configuration, on this panel, adding Jev's
entry filter and exit hook to the mechanical O'Neil rules made results worse,
consistently. What it does not support: any estimate of how the 49 genuinely
missing securities would have changed either arm.

## Related measurements

| effect | magnitude |
|---|---|
| deleting 49 tickers, rules-only equity | sd $17,952 |
| deleting 49 tickers, **paired** Jev − rules | mean −$23,315, sd $17,928 |
| prompt wording, semantically equivalent variants | $45,752 spread |
| interest never earned on 31.5% average cash | $9,243 |

These are not directly comparable to one another and should not be read as a
signal-to-noise ratio. They are four separate sensitivities, each measured
against its own manipulation.

## What would make the question answerable

- A data source that retains delisted securities, and an identity map so
  symbol changes join rather than vanish.
- Interest on idle cash, so a 31.5%-cash arm is not handicapped against a
  fully-invested benchmark.
- Pre-registered prompt paraphrases, reported as a distribution.
- More positions or more trades, so one name matters less. With 5 slots and
  22 buys a year, individual luck dominates.
