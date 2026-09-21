# O'Neil's published rules, as used in the criteria

Consulted 2026-09-20 to replace criteria previously written from recollection.
`src/jev.py` cites this file. Where a number here disagrees with the code, the
code is wrong.

| Rule | Value |
|---|---|
| Prior uptrend before a base | ~30% or more |
| Cup / cup-with-handle | ≥ ~7 weeks; depth 12–33% in a normal market, deeper in bear markets |
| Flat base | ≥ 5 weeks; depth < 15%; buy point at the high of the structure |
| Double bottom | ≥ 7 weeks; depth < 40%; **buy point is the middle peak of the W**, not the old high; second low undercuts the first |
| IPO base | 7 days to ~5 weeks; depth < 20% (up to ~50% in some markets); buy point at the base high |
| Handle | forms in the **upper half** of the base, drifts **down** on contracting volume, ≥ 1 week |
| Breakout volume | ≥ 40–50% above average |
| Buy zone | up to ~5% above the pivot; beyond that the stock is extended |
| Protective stop | 7–8% below the **purchase price** |
| Base count | third base and beyond fails more often — the story is widely known |

## Known gaps between these rules and this implementation

1. **The pivot is a fixed 13-week high.** That is correct for a flat base but
   wrong for a cup-with-handle (the handle high) and wrong for a double bottom
   (the middle peak). The criteria therefore ask Jev to judge where the buy
   point is rather than assuming the 13-week high is it, but the *candidate
   pool* is still generated from the 13-week high, so genuine double-bottom
   buy points below that high are never offered.
2. **Base counting is absent.** Nothing tracks whether a stock is on its first
   or fourth base, so the late-stage downgrade can only be inferred from the
   bars Jev sees.
3. **C, A and I of CAN SLIM are absent** — earnings growth, new products,
   institutional sponsorship. This is a price-and-volume subset, and results
   should be described that way.

## Sources

- [LuxAlgo — O'Neil Base Analysis](https://www.luxalgo.com/library/concept/oneil-base-analysis/)
- [LuxAlgo — Cup-with-handle Base](https://www.luxalgo.com/library/concept/cup-with-handle-base/)
- [LuxAlgo — Double-bottom Base](https://www.luxalgo.com/library/concept/double-bottom-base/)
- [TraderLion — The Flat Base Pattern](https://traderlion.com/technical-analysis/the-flat-base-pattern/)
- [TraderLion — 8 Chart Patterns by William O'Neil](https://threadreaderapp.com/thread/1498771599763423238)

These are secondary sources summarising *How to Make Money in Stocks*. They
are not the book. A reviewer with the primary text should check the numbers
above before any of this is relied on.

## Prompt defects found by review, 2026-09-20

An external review of the rebuilt criteria found four defects. All four were
reproduced before being fixed; the reproductions are in `src/test_delegation.py`
and in the verification below.

| # | Defect | Evidence | Fix |
|---|---|---|---|
| 1 | Routine holding reviews opened by telling Jev "the mechanical rule is about to sell it", and offered only a deadline to defer. No rule is pending on a routine review. | `review_holding()` stripped the sentence with a string replace containing a newline the rendered prompt never had; the replace matched nothing on every call. | `describe_position()` takes `sessions_left=None` for a routine review and renders a different opening and closing line. The framing is a parameter, not post-hoc surgery. |
| 2 | Every `faulty` assessment was discarded. | The loader's allowed set still read `invalid`, the label's name before the criteria were rebuilt. `choice_of` raised, `work()` returned `None`, and the row vanished. The assessment file held **0 faulty rows in 13,550** and 8,848 rows were simply missing. | The allowed set is now derived from `J.ASSESS["setup"].criteria`, so the loader cannot disagree with the prompt. Failures are counted and printed by class instead of returning `None`. |
| 3 | Every assessment prompt asserted "50-day average is above the 150-day, above the 200-day, 200-day rising" as fact. | True of the old candidate pool, which was filtered on `trend_ok`. The selection pool only requires price above the 200-day: the sentence is **false for 10,071 of 22,398 rows (45%)**. Jev was told each stock had passed a screen it had failed. | `_ma_stack()` states the row's measured stack and the actual 200-day slope. |
| 4 | Jev could answer `none` and the portfolio bought anyway. | `JEV_SELECT` and `NEARMISS_MODE` drew on the same slots in sequence. A refusal left `pending_buys` empty, so `spare` stayed at the full slot count and the mechanical near-miss quota filled it. Replay over 2022 with every answer mocked to `none`: **29 buys**. | The two are separate arms. With `JEV_SELECT` on, the near-miss path does not run, and a refusal is logged. Same replay now buys 0. |

Defects 2 and 3 invalidated the assessment run that was in progress when the
review arrived; it was discarded and re-run. Defect 3 is the one that matters
most for anything measured before this date: the model was answering questions
about a stock it had been given a false fact about.


## Correction, 2026-09-21

This table previously said the protective stop sits 7–8% below the **buy
point**. It is 7–8% below the **price actually paid**. The distinction matters
precisely when it is easiest to get wrong: buying 4% above the pivot and then
stopping 7% below the pivot is an 11% loss, not the 7% the rule exists to cap.

`Position.stop` in `src/backtest.py` has always used the fill price, so the
implementation was already correct and was NOT changed to match the sentence.
Only the sentence was wrong. Source: IBD's 20 rules,
<https://shop.investors.com/images/promotional/20-Rules_102808.pdf>.
