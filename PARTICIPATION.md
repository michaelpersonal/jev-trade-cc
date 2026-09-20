# Why the portfolio stops participating

Prompted by an external critique that my earlier framing — "stock picking is
fine, stops caused the missed winners, this is O'Neil's limit" — was not
supported by the numbers. It wasn't. This is the attribution done properly.

## Which gate binds, per underinvested day (H2, >20% cash, 331 of 620 days)

| Gate | Days | % | Mean cash |
|---|---|---|---|
| 1. Market rule — RED, no buying | 55 | 16.6% | 81.2% |
| 1. Market rule — slot cap binding (YELLOW=2) | 84 | 25.4% | 52.1% |
| **2. No stock passed the entry screen** | **153** | **46.2%** | 64.6% |
| 3. Candidates existed, partially filled | 39 | 11.8% | 59.2% |

No days where candidates existed and ranking silently dropped them all.

## Gate 4 — re-entry after an exit

67 H2 exits. **52 never re-qualified.** 15 did (median 42 calendar days later);
only 7 were re-bought. Of 30 stop-outs, 6 re-qualified and 3 were re-bought;
the average name returned +25.9% from our exit price to the end of H2, and six
of them gained more than 50% after we sold.

### The GLW case, which refutes the stop hypothesis

Sold 2024-12-20 on a **50-day break at −0.53%** — not a stop. Re-qualified
2025-01-21 with RS 88, regime GREEN. The book held 4 of 5, **one slot open**,
three candidates competing. PWR won it on **RS 89 versus 88**, a one-point gap
in a rounded integer. GLW then returned **+221%** from our exit price.

GEV *was* a −7% stop, but it **never re-qualified** — the screen kept us out
afterwards, not the stop.

Neither missed winner is explained by holding period. Both are participation
and re-entry gates.

## Testing the gates separately, protective stops untouched

**Capacity is not the constraint.** More slots is worse and *reduces* exposure,
because sizing is equity ÷ slots: 5 → +24.2% at 57% exposure, 8 → +21.6% at
54%, 12 → +6.9% at 48%. Slot count and position sizing are coupled, which is
itself a design flaw worth separating before capacity can be tested cleanly.

**YELLOW is a noise dial.** Full-period improves as it loosens (+24.2% → +41.3%
→ +34.2%) while out-of-sample moves the other way (+5.6% → +1.8% → +1.4%).

**Re-entry speed controls participation, but not return.** Exposure rises
monotonically as the suppression window shortens — 57, 60, 61, 63, 64, 65, 66%
for 25, 20, 15, 10, 7, 5, 3 days — confirming the mechanism. Return does not:
5 days gives +48.0% with a −17.9% drawdown, 7 days gives +15.2% with −27.8%.
H2 swings from −1.6% to +30.0% between adjacent cells. A lucky cell, not an
optimum.

## Corrections to the record

- **"Stops caused the missed winners"** — false. Neither GLW nor GEV supports
  it; see above.
- **"Stock picking is fine"** — overstated. Selection contributed −13.9pp in
  2024, −0.5pp in 2025, +11.2pp in 2026. Unstable around zero, not fine.
- **"An unavoidable limit of O'Neil"** — not established. The dominant gate,
  an empty screen on 46% of underinvested days, follows from two of my own
  choices: a 586-name large-cap universe for a method built to scan thousands,
  and a 25-day re-signal suppression that is mine, not his. The regime filter
  does earn something — removing it collapses selection by 18.9pp — but that
  is a separate finding.

## What the next attempt should target

The empty screen, not the exposure dials. The routes that add signal supply
without loosening quality are a wider universe, and O'Neil's secondary entry
points (pullback to the 50-day, three-weeks-tight). Re-entry speed is real
mechanically but no setting of it survives the stability test.
