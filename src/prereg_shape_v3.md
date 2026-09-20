# Pre-registration: chart-shape judgment, third framing — FROZEN 2026-09-20

Written before the run. This is the **third** framing tested against the same
637-candidate pool, and that has to be stated plainly: researcher degrees of
freedom are accumulating, and a positive result here is weaker evidence than a
positive result on the first try would have been.

## Why re-run at all

The v2 result (rank correlation −0.077 at 60 days) is not trustworthy. It was
produced against:

1. **Contaminated RS values** — relative strength was ranked over every name
   that was ever an index member, not the population that existed that day.
   Fixed; the buy-signal count fell 398 → 353.
2. **A leading prompt** — the state opened *"Weekly price bars for a stock
   that broke out today"* and two of the three questions presupposed a
   breakout, before asking whether a genuine base existed.

Both are now fixed. This re-run tests the same hypothesis on clean inputs.

## Hypothesis

Jev's judgment of base quality, from serialized weekly bars, carries
information about forward return beyond the mechanical `rs_rating`.

## Frozen analysis

- Metrics: Spearman rank correlation of each Jev output against forward excess
  return at **20 and 60 sessions**, measured from the next session's open.
- Comparator: mechanical `rs_rating` on the identical rows.
- Quintile table of forward return by `shape_quality`.
- **Reported separately for 2022-01→2024-03 and 2024-04→2026-09.** A result
  that does not hold in both halves is not a result.

## Decision rule

The judgment carries information only if rank correlation is **positive and
exceeds `rs_rating` in both halves at both horizons**. Anything less is
recorded as null.

## Stopping rule

This is the last framing tested on this pool. If it is null, the conclusion is
that Jev's chart-shape judgment does not predict returns *here*, and further
prompt variants would be fishing. No v4.
