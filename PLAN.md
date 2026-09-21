# Work plan: fix the exit framing and the entry state

Reviewed before starting. Six flaws in the first draft are corrected below and
marked **[FIXED IN REVIEW]**.

## Measurement discipline (applies to everything)

A single final-equity number is inside +/-$18k of noise: the deletion
experiment measured that, and a $7,183 move came from six decision flips.
**No change in this plan is to be judged by a single backtest number.** The
paired jackknife is the verdict. Arms are compared against the S&P only.
Nothing is tuned on a result.

---

## 1. Exit framing

The override prompt puts the conclusion in the state -- "a mechanical rule has
already decided to SELL" -- and Jev ratifies it. Measured on the cache, same
model, same positions, only wording differing:

| framing | keeps the position | mean confidence |
|---|---|---|
| neutral, hold/sell/unclear | 46.0% | 0.38 |
| override, override/let_it_sell | 2.4% | 0.90 |

This is the `is_monday = 0.96` failure: assert a premise in the state and Jev
agrees with it, confidently.

- [x] **1.1** Make `JEV_EXIT_MODE=2` (neutral `HOLDING_REVIEW`) the exit path.
      The standing stops stay in code and fire regardless: a calibrated
      probability is not a risk limit.
- [x] **1.2** Wire `pol.review_abstain`. It is declared in `policy.py` and
      never read; `unclear` currently keeps the position by falling through an
      `if/elif`, which is the right outcome by accident. Record an abstention
      distinctly from a confident hold.
- [x] **1.3** An inference error must not become a hold.
      **[FIXED IN REVIEW]** The first draft said "don't hold" without saying
      what to do instead. Correct behaviour: fall back to the mechanical
      50-day rule, record it as a failure attributable to the run and not to
      Jev, and count it. A run whose error rate exceeds a declared threshold
      is reported as incomplete rather than as a result.
- [x] **1.4** Bound consecutive **abstentions**, not holds.
      **[FIXED IN REVIEW]** The first draft said "bound consecutive holds".
      That is wrong and anti-O'Neil: holding a winning leader for months is
      the strategy working, and capping it would force arbitrary sales. What
      needs bounding is repeated *unclear*: after N consecutive abstentions on
      the same position, fall back to the mechanical rule. Freeze N before
      measuring.

## 2. Exit state

Neutral framing runs at 0.38 confidence against 0.33 uniform -- near a coin
flip. Fixing 1 without 2 yields an autonomous decider that is guessing.

- [x] **2.1** Earnings into `describe_position`, from the same point-in-time
      SEC facts the entry uses. O'Neil sells on earnings deterioration.
- [x] **2.2** Relative-strength **direction**, not only today's rank. The
      level is not the sell signal; the deterioration is.
- [x] **2.3** State the up-day versus down-day volume comparison explicitly.
      It is the shakeout/breakdown discriminator and is currently only
      implicit in ten bars.
- [x] **2.4** Widen the bar window, with a cap.
      **[FIXED IN REVIEW]** The first draft said "life of the position",
      which is unbounded -- a 200-session holding would emit 200 lines and
      inflate every prompt. Correct design: the last 20 daily bars in full,
      plus a compact since-entry summary (weeks held, peak gain, max
      give-back, count of heavy-volume down days).

## 3. Entry state

16 rebased weekly bars. `pattern` sits at 0.257 against 0.200 uniform.

- [x] **3.1** Daily bars through the handle and breakout, **capped**.
      **[FIXED IN REVIEW]** A base runs 5-13+ weeks; emitting every daily bar
      would be 25-65+ lines on top of the weeklies. Correct design: keep the
      16 weekly bars for the long structure and add the most recent ~20 daily
      bars, which is where the handle and the breakout live.
- [x] **3.2** Base count, **computed in code**.
      **[FIXED IN REVIEW]** The first draft did not define it or say who
      computes it. Sixteen weekly bars cannot establish a multi-base history,
      so Jev must not be asked to infer it. Definition: the number of prior
      completed breakouts for this ticker since the current advance began,
      where the advance begins at the last session the close was below the
      200-day average. Computed in `strategy.py`, carried on the Anchor, and
      stated in the prompt. O'Neil: late-stage bases fail more often.
- [x] **3.3** Make the `extended` label reachable.
      **[ADDED IN REVIEW]** Not in the first draft. `extended` never fires in
      96 exam cases and 6 of 12 genuinely extended setups return `valid`, so
      an entry criterion O'Neil is most explicit about is dead. It is an entry
      defect, and bundling it here saves a second ~$2 assessment re-run.
      Needs an explicit precedence rule between valid / extended / faulty.

## 4. Verify and measure

- [x] **4.1** Cost check on a sample before any full run.
      **[ADDED IN REVIEW]** Not in the first draft. Every item above makes
      prompts longer, and the assessment pass is 22,398 requests. Price it on
      `--sample 300` first and report the projected full cost.
- [x] **4.2** `test_timing.py` and `test_contracts.py` still pass.
- [x] **4.3** Re-run `run_exam.py`: ASSESS conformance and the selection call.
      **[ADDED IN REVIEW]** The first draft only re-ran the arms. A prompt
      change that improves returns and breaks conformance is not an
      improvement.
- [x] **4.4** Re-run the full assessment artifact (fingerprints change).
- [x] **4.5** Arms against the S&P.
- [x] **4.6** Paired jackknife. This is the verdict, not 4.5.

## RESULT 2026-09-21 (was blocked on credits; now run)

All 17 items complete. The pre-registered sample proof passed on all three
predictions (see prove_fix.py), the full assessment ran clean at 22,398/22,398
with zero errors, and the exam holds conformance. The paired jackknife is the
verdict and it does NOT support the headline:

    undeleted panel      Jev - rules = +$37,512
    across 12 draws      mean +$4,048, sd $25,029, Jev ahead in 7 of 12

Jev beating the S&P by $48,246 on the real panel is one favourable draw, not
a demonstrated edge. What the fixes DID achieve is visible against the same
measurement before them: the paired difference was -$23,315 with Jev behind
in 11 of 12. The work moved a reliable loss to a coin flip, and did not
produce a demonstrable gain.

Note also that the paired standard deviation ($25,029) is LARGER than either
arm alone ($17,952). Jev's decisions add variance rather than cancelling it.

That failure also exposed a defect, now fixed: the manifest's `partial` flag
records only whether --sample was used, so a run that exhausted its credits
half way wrote partial=false with 51% coverage and would have loaded as a
complete universe -- the 10,944 absent rows being indistinguishable from
"nothing qualified that day". The loader now refuses any artifact below
COVERAGE_MIN.

## Known-open, deliberately NOT in this plan

- Earnings are announced before filed, median 35-day lag; 8-K Item 2.02 closes it
- 49 tickers with no price data (37 genuinely delisted, 12 symbol changes)
- Idle cash earns nothing, worth ~$9,243 against a fully-invested benchmark
- YELLOW documented as "half exposure", actually 40%
