# Near-miss adjudication — result

Executed against `src/prereg_nearmiss.md`, frozen before any return was computed.

## Primary question: does Jev beat an equally-sized dumb relaxation?

**No.** The pre-registered rule required arm A to beat arm B on the full period,
in both halves, and out of sample.

| Arm | Full | H1 | H2 | Max DD | Exposure | OOS | Fills | Near-misses |
|---|---|---|---|---|---|---|---|---|
| C — baseline, strict screen | +24.2% | +19.0% | +8.1% | −21.2% | 57% | +5.6% | 205 | 0 |
| **A — Jev adjudicates** | +74.0% | +23.3% | +50.0% | −20.1% | 69% | +90.6% | 221 | 72 |
| **B — mechanical, count-matched** | **+83.3%** | +23.3% | **+56.9%** | −21.5% | 68% | +57.9% | 221 | 67 |
| D — mechanical, unmatched | +70.2% | +23.3% | +43.1% | −20.8% | 68% | **+106.5%** | 227 | 73 |
| S&P 500 | +59.5% | +9.5% | +45.9% | −25.4% | 100% | — | 1 | — |

A loses to B on the full period (−9.3pp) and in H2 (−6.9pp), ties in H1, and
wins only out of sample — where D, which applies no judgment whatsoever, beats
both. **Fails.** Cost: 229 calls, $0.012.

This is the fourth pre-registered test in which Jev's chart-based judgment shows
no value. Consistent with the other three.

## Secondary: the relaxation itself looks transformative, and isn't

Opening the screen takes the run from +24.2% to +70–83%, past the index, with
drawdown unchanged. It survives a 17× range of band widths (pool 195 → 3,355,
full-period +63% to +92%) and improves both halves and out of sample.

Isolating the cause: the single largest factor is **not** the quality bands but
dropping the first-cross de-duplication. Buying *any* close above the 13-week
pivot instead of only the first lifts the run from +24.2% to +48.5% and exposure
from 57% to 67% — i.e. the strategy becomes trend-continuation rather than
breakout.

### Why it should not be believed

Of the **54 names traded only by the near-miss arm, aggregate P&L is $1,807** —
while **MRVL alone contributed +125.87% / $25,468**. The other 53 uniquely
added names lost roughly $23,700 between them.

Both arms are entirely carried by a handful of trades:

| | n | Total | ex top 1 | ex top 3 | ex top 5 | Median trade | Win rate |
|---|---|---|---|---|---|---|---|
| strict | 101 | $24,649 | $5,512 | −$15,158 | −$29,543 | −4.57% | 33.7% |
| near-miss | 111 | $43,200 | $17,732 | −$12,045 | −$26,768 | −4.06% | 34.2% |

Excluding the top five trades, **both configurations lose roughly $27–30k**.
The median trade is about −4% in each. This is O'Neil's own thesis operating as
designed — cut losses, let a few winners pay for everything — but it means any
comparison between these variants is a comparison of who caught which lottery
ticket, not of selection skill.

The H2 decomposition says the same thing: the near-miss arm shows +28.0pp of
apparent "selection alpha" at the same exposure as the plain relaxation, which
is MRVL.

## Conclusion

- Jev's adjudication of near-misses: **no value**, by the frozen rule.
- Relaxing the screen: **raises participation reliably** (exposure 57% → 68%),
  but its return advantage rests on one trade and should not be shipped on this
  evidence.
- The honest next test is not another parameter. It is whether the relaxation
  survives on data that does not contain MRVL — a wider universe, or a
  different period.
