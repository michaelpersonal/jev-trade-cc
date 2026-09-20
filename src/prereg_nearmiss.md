# Pre-registration: near-miss adjudication — FROZEN 2026-09-20

Written before any return under it was computed.

## Why

Gate attribution (`PARTICIPATION.md`) shows the dominant reason the book sits in
cash is that **no stock passes the entry screen** — 46% of underinvested days in
H2. Jev currently sits *downstream* of that screen as a veto and re-ranker: the
decision ledger shows it accepted 108 of 109 candidates, so it cannot increase
signal supply and cannot touch this gate.

This experiment moves it upstream.

## Near-miss definition — frozen

A name is a near-miss on day `t` when it satisfies **every** structural
requirement — close above the 13-week pivot, the full stage-2 trend template,
price ≥ $10, ≥ $20M average turnover, index membership — and fails **exactly
one** of three relaxable tests, inside a stated band:

| Test | Strict | Near-miss band |
|---|---|---|
| Breakout volume | ≥ 1.40× the 50-day average | 1.15× – 1.40× |
| Relative strength | ≥ 80 | 65 – 79 |
| Base depth | 8% – 35% | 5% – 8%, or 35% – 45% |

Pool: **2,058 candidates on 722 days**; 514 of those days carry no strict
signal at all.

## Arms — identical data, execution, stops and sizing

| Arm | Near-misses admitted |
|---|---|
| **C — baseline** | none; the shipped strict screen |
| **A — Jev** | Jev answers buy/skip on each; buys are ranked by a Score |
| **B — mechanical, count-matched** | the **same number Jev admitted that day**, ranked by RS |
| **D — mechanical, unmatched** | fill every spare slot, ranked by RS |

Strict candidates always take slots first; near-misses only fill what is left.
The 7% stop, the 15% trailing stop and equity÷5 sizing are unchanged in all
four arms.

**B is the control that makes this a decision-value test rather than another
return-prediction test.** A beats a dumb relaxation of identical size, or it
does not.

## Reported, all of them

Full period, both halves, the seven walk-forward out-of-sample folds, max
drawdown, average exposure, trade count, and the number of near-misses each arm
admitted.

## Decision rule

Jev's adjudication has value only if arm A beats arm B **on the full period and
in both halves and out of sample**. Beating only arm C means the relaxation
helped, not the judgment — D is there to show that separately.

## Stated in advance

The prior is unfavourable. Every exposure increase tested so far (YELLOW slot
count, re-entry window, slot count) has been a noise dial, and Jev's chart
judgment showed no predictive power across three pre-registered framings. A
null here is the expected outcome and will be reported as such.
