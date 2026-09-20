# Pre-repair outputs — DO NOT CITE

Generated before the measurement defects found in `codex-review.md` were fixed.
Kept only so post-repair numbers can be diffed against them.

Known defects in these files:
- Position limit gating open fills was read from the same day's CLOSE regime
  (lookahead). Codex's probe: changing the later close flips a buy 1 -> 0.
- RS rating ranked over the full ever-member panel, not the population that
  was actually in the index on that date.
- `sharpe` is CAGR / annualised volatility, not a Sharpe ratio.

Baseline at time of capture: $130,828 (5 positions, 15% trailing stop).
Commit: 0a6ce61
