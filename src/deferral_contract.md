# Exit-deferral contract v1 — FROZEN 2026-09-20

Written before any return under it was computed, in response to finding 2 of
`codex-integration-review.md`: a hold answer previously had no expiry, so the
same exit could be vetoed for the rest of the run.

## Episode

An **episode** opens the first day the mechanical exit qualifies — the close is
below the 50-day average for `need` consecutive days (2 normally, 1 in RED).

Within an open episode, Jev is asked each day whether the weakness is a
shakeout or a breakdown.

## Bounds — all fixed in advance, none tuned

| Rule | Value |
|---|---|
| Maximum deferral | **10 trading sessions** from the episode's first day |
| `sell` answer | executes at the next open, episode ends |
| Expiry | at session 10 the position is sold at the next open **regardless** |
| Reset | a close back above the 50-day average ends the episode and clears the counter; a later breach opens a **new** episode |
| Protective stops | the 7% hard stop and the 15% trailing stop stay in code and fire inside an episode exactly as outside it |

10 sessions is two calendar weeks, chosen a priori as the longest a "shakeout"
can reasonably be called one. It was not selected by looking at returns.

## What Jev is told

The state names the permitted action and its remaining horizon, and the
distance to the active protective stop, so the judgment is made against the
authority actually on offer rather than an open-ended one.

## What Jev cannot do

Jev can only keep a position that risk limits already allow. It cannot widen a
stop, add to a position, re-enter, or extend the deadline. Every deferral is
recorded in the decision ledger with its episode id, so the delegation is
auditable after the fact.
