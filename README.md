# Jev — O'Neil momentum backtest, 2022–2026

> **Revised 2026-09-20.** An external review (`codex-review.md`) found three
> measurement defects — a lookahead in the position limit gating open fills, a
> chandelier stop built from the current bar's ATR, and relative strength
> ranked against every name that was *ever* an index member. All are fixed;
> `src/test_timing.py` guards the timing boundary and is proven to fail against
> the original defect. Repairs cost 6.6 points. Pre-repair outputs are in
> `data/pre_repair/` and must not be cited. Numbers below are post-repair.

$100,000, long only, no margin. Benchmarked against S&P 500 buy-and-hold.
Replay page: `web/index.html`.

## Current configuration

Five positions. Entry is O'Neil unchanged: RS 80+, a first close above a
5–13 week base within 15% of the 52-week high, on 1.4x average volume, gated
by a three-state market regime read off the S&P 500.

Exit departs from O'Neil in one place — his fixed 20–25% profit target is
replaced by a **15% trailing stop** from the highest close since entry. The 7%
hard stop, the 8-week rule and the 50-day-line break are unchanged.

The 15% is not tuned. Anything from 15% to 25% is the same decision; the
trailing stop's only real contribution is that it stops capping winners.

## Results

| | Jev (shipped) | Jev (20–25% target) | S&P 500 |
|---|---|---|---|
| Final value | **$170,234** | $115,640 | $159,500 |
| Total return | **+70.2%** | +15.6% | +59.5% |
| CAGR | **+12.0%** | +3.1% | +10.4% |
| Max drawdown | **−20.8%** | −25.1% | −25.4% |
| Return ÷ volatility | **0.74** | 0.22 | 0.61 |

**Read `NEARMISS_RESULT.md` before citing the margin over the index.** It rests
heavily on one position (MRVL +125.9%, $25,468); the 54 names the relaxed screen
uniquely traded netted $1,807 in total. Strip the best five trades from either
configuration and both lose $27–30k. That is O'Neil's design working as intended,
but it means the edge is one name wide.

101 closed trades, 33.7% win rate, profit factor 1.31. NVDA +54% (70 days),
best trade INTC +88%. With O'Neil's fixed target the strategy loses money.

"Return ÷ volatility" is CAGR over annualised volatility. It was previously
mislabelled "Sharpe"; no risk-free rate is subtracted.

Still 29 points behind the index. Split in half, the reason is not uniform:

| Period | Jev | S&P 500 |
|---|---|---|
| 2022-01 .. 2024-03 | **+28.6%** | +9.5% |
| 2024-04 .. 2026-09 | +6.8% | +45.9% |

It beat buy-and-hold over the first two years and broke afterwards.

## The participation fix (shipped default)

`S.NEARMISS_MODE = 3`. The strict screen — a *first* close above the 13-week
pivot — admits 0.09% of stock-days and produces **22 buys a year against the 39
needed to keep five slots full**. That shortfall, not the market filter, was the
cash. Admitting near-misses (one relaxed quality bar, any close above the pivot)
takes exposure from 57% to 68% and the run from $124,242 to $170,234.

Jev was tested against a count-matched mechanical control on exactly this and
**lost** (+74.0% vs +83.3%). The fix is mechanical; no model is involved.

## The market filter has no timing skill

Holding the same *average* exposure constantly beats the filter's actual path:

| Window | Avg exposure | Actual path | Constant | Timing |
|---|---|---|---|---|
| Full run | 57% | +17.5% | +32.9% | **−15.4pp** |
| H1 | 46% | +9.2% | +5.3% | +3.8pp |
| H2 | 64% | +12.0% | +28.4% | **−16.4pp** |
| 2022 (bear) | 10% | −8.0% | −1.9% | **−6.1pp** |

2022 was saved by the *level* of exposure, not by when it was raised. Keep the
RED block only because signals taken in RED tape are bad — removing it costs
19 points of selection — not because it times anything.

## Why it used to hold 45% cash

Measured per day, not assumed:

| Cause | Share of days | Mean cash | Contribution |
|---|---|---|---|
| Regime RED — no buying allowed | 24.7% | 91.8% | **23 pts** |
| Regime YELLOW — book halved to 2 | 19.5% | 56.4% | **11 pts** |
| GREEN — genuine signal shortage | 55.8% | 20.9% | 12 pts |

**Three quarters of the cash is the market filter standing down on purpose**,
not an empty screen. On GREEN days the book holds 3.9 of 5 at 21% cash.

The RED block earns its keep — disabling the filter entirely drops H2 to +3.2%
and deepens max drawdown to −27.6%. The YELLOW halving is the questionable
part, and it is not O'Neil's rule; it is an invention of this implementation.

`S.YELLOW_SLOTS` sweeps it. Full period favours 4 slots (+49.4% vs +30.8%) and
improves both halves, **but the out-of-sample column does not confirm it**:

| YELLOW slots | Full | H1 | H2 | OOS (2023-07+) |
|---|---|---|---|---|
| 1 | +25.0% | +22.7% | +3.9% | +11.6% |
| **2 (shipped)** | +30.8% | +28.6% | +6.8% | **+13.0%** |
| 3 | +32.4% | +27.1% | +19.7% | +5.3% |
| 4 | +49.4% | +35.6% | +20.3% | +15.1% |
| 5 | +47.5% | +29.3% | +13.1% | +7.1% |

A one-slot move swings OOS by ten points in either direction. Exposure is a
dial that amplifies whatever the period does, not an edge — in fold 1 more
exposure lost more, in fold 3 more exposure won more. Left at 2 pending more
data.

## Known limits

- **Signal starvation.** 398 buy signals in 4.7 years across 586 large caps —
  about 1.4 on the one day in four that has any. Real, but only ~26% of the
  cash. O'Neil traded all listed US stocks.
- **C / A / I are not implemented.** Earnings growth and institutional
  sponsorship need point-in-time fundamentals unavailable for delisted names.
- **49 of 635 tickers** left no usable history after delisting — residual
  survivorship bias, leaning slightly favourable.

## Tested and rejected

Both were built to fix the post-2024 breakdown. Both are kept in the tree
(`src/macro.py`, `src/groups.py`) but **off by default**, because neither
improves both halves:

| Variant | Full | 2022–24 | 2024–26 | Exposure |
|---|---|---|---|---|
| **Baseline (trail 15%)** | **+30.8%** | **+28.6%** | +6.8% | 55% |
| + macro veto | +12.8% | +9.9% | +8.5% | 48% |
| + macro symmetric | +9.6% | +4.5% | +10.4% | 51% |
| + leading groups (top 50%) | +9.6% | +11.1% | +12.3% | 51% |
| + leading groups (top 25%) | +9.7% | +5.8% | +8.1% | 43% |

Both overlays reduce exposure. That helps slightly in the second half where
breakouts were failing, and costs heavily in the first where they worked. On a
strategy already half in cash, buying protection with exposure is a bad trade.

The sector filter has a second problem: breakouts **already** cluster in
leading groups — 174 of 398 signals are in the top quartile, 22 in the bottom —
so it mostly removes signals RS-80 was never going to surface anyway.

## Walk-forward

`src/walkforward.py`. Fit on trailing 18 months, trade the next 6, step 6.
Seven out-of-sample folds, 2023-07 → 2026-09:

| | Final | Beat constant |
|---|---|---|
| Walk-forward (re-fit each fold) | $84,783 | 1 / 7 folds |
| Fixed setting, never touched | **$105,621** | — |
| S&P 500 | $172,044 | — |

Re-fitting **lost 10 points** to leaving the parameters alone, and picked a
different configuration in 6 of 7 folds. The parameters are noise. Note this
window starts July 2023 and so excludes 2022, the strategy's best year.

## Next

The post-April-2024 breakdown is still the open question, and nothing tried so
far touches it. Every filter added makes the binding constraint worse, because
the constraint is exposure, not selection. The only untested direction that
*raises* exposure is a wider universe (more names → more bases → a fuller
book), or O'Neil's secondary entries — pullback to the 50-day, three-weeks-tight
— which add buy points without loosening quality.

## Layout

    src/universe.py    point-in-time index membership from Wikipedia revisions
    src/data.py        daily OHLCV panel via yfinance
    src/strategy.py    O'Neil rules as vectorised indicators
    src/backtest.py    day-by-day simulation
    src/metrics.py     performance statistics
    src/run_all.py     driver; writes web/data.js
    web/index.html     interactive replay page

## Rebuild

    python3 -m venv .venv && .venv/bin/python -m pip install pandas numpy yfinance pyarrow requests lxml
    .venv/bin/python src/universe.py        # ~40 Wikipedia revision snapshots
    cd src && ../.venv/bin/python data.py   # ~586 tickers of daily bars
    ../.venv/bin/python backtest.py         # writes signals.parquet + result.json
    ../.venv/bin/python run_all.py          # writes web/data.js

Strategy parameters live at the top of `src/strategy.py`. `TRAIL_PCT`,
`TRAIL_ATR` and `PROFIT_TARGET` are mutually exclusive; the 7% hard stop
always applies.

## Timing contract

Signals on day `t` use bars up to and including day `t`'s close. Entries and
trend-break exits fill at day `t+1`'s open. The 7% stop and the trailing stop
are standing orders and fill intraday against day `t`'s high/low; a gap through
fills at the open. The trailing level on day `t` is built from peaks through
day `t-1`'s close. The universe on day `t` is the most recent Wikipedia
snapshot dated on or before `t`.
