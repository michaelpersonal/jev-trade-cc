# Decision-value contract v1 — FROZEN 2026-09-20

Written before any post-event return was computed. Do not edit after seeing
results; if it proves inadequate, say so and version it.

## Event

One passage in `data/guidance_corpus.parquet`, i.e. one original 8-K.

## When we may trade

`acceptanceDateTime` (Eastern, from EDGAR's submissions API) is when the filing
became public. The entry price is the open of the **first regular session that
begins strictly after that moment**:

- accepted before 09:30 on a session day -> that session's open
- accepted at or after 09:30 -> the next session's open

This deliberately forgoes the announcement move. The whole question is whether
anything is left *after* the market has seen the filing.

## Action

Enter at that open, hold **H** sessions, exit at the close of session H.
`H in {1, 5, 20}`. All three are reported; none is selected afterwards.

Returns are **excess over SPY** across the identical window. A negative excess
return means the market kept marking the name down after publication — i.e.
shorting on the signal would have paid.

## Signals compared (same policy, different trigger)

| Signal | What it tests |
|---|---|
| Jev `noul >= 0.80` | the model's judgment |
| Gold label | ceiling: perfect interpretation |
| Regex lexicon | can a cheap rule do as well |
| All events | base rate, i.e. no signal at all |
| Random, same firing rate, 1000 draws | the null |

The 0.80 threshold comes from the **interpretation** evaluation, where accuracy
above 0.8 was 100% at 90% coverage. It was not chosen by looking at returns.

## Costs

10 bp round trip (5 bp per side), matching the equity backtest. No borrow fee
is modelled, which flatters any short. Named as a limitation, not corrected.

## Decision rule

Jev's judgment has decision value only if its excess return beats the
all-events base rate **and** falls outside the central 95% of the random-signal
distribution **at two or more horizons**. One horizon out of three is what
noise looks like.

## Stated in advance

n = 129 events, ~48 gold positives. This is a small sample with overlapping
20-session windows and repeated issuers. A null result will not mean "no
effect exists"; a positive result at one horizon will not mean "an edge
exists". Report confidence intervals, not point estimates alone.
