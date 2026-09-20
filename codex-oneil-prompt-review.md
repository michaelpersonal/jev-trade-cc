# Does the current setup teach Jev O'Neil?

Review date: 2026-09-20. Read-only review of HEAD `09085e6` plus the current uncommitted prompt/default changes. No trading code or prompts changed; no new API calls made. The review examines the actual runtime questions, serialized evidence, mechanical gates, cached responses and tests, not just the prose in the architecture diagram.

## Verdict

**Prompting is the supported way to specialize Jev, but this setup has not demonstrated faithful application of O'Neil.** It is a partially specified price-pattern heuristic inside a materially customized strategy. The latest prompts are more descriptive than their predecessors, but have a documented Score-contract violation, unavailable evidence, incomplete doctrine, ambiguous action criteria, and no independent strategy-comprehension evaluation.

This is not a finding that Jev cannot learn these distinctions in context. It is a finding that neither its demonstrated competence nor this input/policy design justifies that claim yet. A profitable backtest would not resolve those defects; an unprofitable one would not prove the model cannot recognize a base.

| Dimension | Assessment | Evidence |
|---|---|---|
| Specialization mechanism | Appropriate in principle | Jev supports domain rules in request instructions/criteria and reference material in state |
| Fidelity to the intended method | Partial, not full CAN SLIM | Generic price/volume narrative, bespoke pivots/regime, missing fundamental inputs |
| Entry rubric | Needs revision | Multi-dimensional Score; top level refers to other levels; buy asks unspecified cash outperformance |
| Exit evidence | Insufficient for its own question | No daily path, close-in-range, base location or recovery history |
| Runtime authority | Bounded but mixed | Protective stops remain code; mode-3 near-miss purchases bypass entry Jev |
| Engineering guards | Six existing checks pass | Timing, initialization, cache invalidation, deferral cap, malformed answers |
| Actual O'Neil comprehension | Unmeasured | No independent labeled conformance suite found |
| Predictive or economic edge | Separate question | Older prompt results do not validate the new prompt's understanding or profitability |

## 1. What “learning” can mean here

TypeSafe says Jev is not customer-fine-tuned or LoRA-adapted; accounts use shared weights, and requests/responses are not used to train it. Domain specialization therefore lives in the request: relevant reference content, explicit instructions, option definitions and boundary examples. Repeated backtests and cached answers do not teach the next call anything unless the application explicitly changes its supplied context/policy. [Models](https://docs.typesafe.ai/models)

The right unit of instruction is a narrow judgment, not “be William O'Neil.” A compact, source-grounded rulebook should be compiled into task-specific questions and evidence requirements. Examples can illustrate distinctions, but their effectiveness needs evaluation. A whole book in every request is not necessary. TypeSafe warns about irrelevant context, arithmetic, indirection and contradictory criteria. [Known limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

Source doctrine -> explicit scoped policy -> observable evidence -> typed judgment -> deterministic action mapping -> independent evaluation. All six parts matter. Adding better prose addresses only one part.

## 2. Actionable findings

### P1 — The highest Score level cannot inherit “Everything above”

`src/jev.py:341-343` begins its highest criterion with “Everything above.” TypeSafe explicitly states that Score levels are evaluated separately and a level cannot see its neighbors. Thus the purported top level does not actually contain the preceding level's requirements for contraction, breakout confirmation and lack of extension. Its remaining prior-advance/quiet-drift description can match a different situation from what CC intended. [Score specification](https://docs.typesafe.ai/primitives/score)

The same scale bundles shape, depth, extension, volume and prior advance. A good shape with poor volume and a poor shape with strong volume do not have a defined ordering. The API permits using a Score for ranking, but the chosen level descriptions must establish a coherent dimension. A fractional score is a weighted level index, not expected return or probability of trading success. With five criteria the valid range is 0–4; `score_of` currently accepts up to 10. The audit accepts 9, confirming a secondary validation defect.

Required: self-contained levels; separate evidence dimensions where mixed cases cannot be ordered; enforce the actual scale range. Do not just replace “Everything above” while retaining the untested composite meaning.

### P1 — Exit Jev is asked to judge facts it cannot observe

`src/jev.py:351-364` asks about a recovering undercut, repeated closes near lows, distance from a base and prior trend integrity. `describe_position` at 369–395 supplies current MA distances, one day's volume, entry/peak gains and duration, not that evidence.

Read-only probe: two rows with the same close but very different daily highs/lows and base pivots produce **identical serialized exit states**. One close is near the day's low; the other near the high. Jev cannot distinguish them, regardless of model quality. Many price paths also map to the same snapshot. This is an information problem, not something to solve by adding stronger instructions.

Required: supply the relevant trailing daily path plus code-computed close location, volume on declines/rebounds, support/pivot distances and recovery attempts. Distinguish an already observed recovery from a forecast of one. If required evidence is unavailable, return insufficient evidence and let code apply an explicit fallback.

### P1 — The prompt is not an explicit specification of the claimed method

The current entry rubric teaches an orderly-rest narrative, not distinct pattern definitions and buy-point rules. IBD's published material distinguishes cup-with-handle, double-bottom and flat bases, with different geometry, durations and pivots. For example, a handle peak and a double bottom's middle peak are not necessarily the highest high over a fixed 65-day window. [IBD buying guide](https://get.investors.com/wp-content/uploads/2024/08/IBDD-How-to-buy-Stocks-infographic.pdf)

Yet `strategy.py:114-144` fixes the pivot to that window's maximum and filters candidates before Jev sees them. The prompt cannot rescue valid setups excluded by the caller. Conversely, the ordinal rubric can reward a generic attractive rest without establishing that a supported pattern actually exists.

The scope also excludes current/annual earnings, much of the new-product/catalyst evidence, and institutional sponsorship. O'Neil's published framework combines these with technical entries, leadership, market context and sell discipline. [IBD's 20 rules](https://shop.investors.com/images/promotional/20-Rules_102808.pdf)

Required: declare whether this is a full CAN SLIM system or a price/volume subset. Name supported patterns and exceptions, mark unsupported components as unknown, and distinguish source doctrine from project modifications. Existing rules may intentionally differ; they must not be passed off as what Jev learned from O'Neil.

### P1 — The questions mix recognition, forecasts and actions

`src/jev.py:301-309` asks whether buying “beats holding cash,” but supplies no evaluation horizon, payoff criterion or full entry/exit policy. Structural conformity is not the same target as future profitability. There may also be other candidates or near-miss purchases, so declining this stock does not necessarily leave that slot in cash.

The exit prompt says selling a shakeout forfeits an advance and distribution means the move is over. Those are future conclusions, not observable definitions. The sell criterion also couples deterioration to giving back most gains. A sharp adverse break can warrant action while substantial profit remains; the current options do not cleanly cover that case. Neither entry nor exit permits insufficient evidence or a mixed state.

Required: choose the question being measured. First recognize a defined pattern/evidence state. Code maps it to the allowed action under a declared policy. If forecasting is wanted, create a separately defined future event and score it against realized outcomes. Do not equate a Choice probability with profitable-trade odds.

### P1 — The doctrine is not consistently connected to runtime authority

The new defaults set `JEV_ENTRY=True` and `JEV_EXIT=True`, but retain `NEARMISS_MODE=3`. At `backtest.py:398-435`, mode 1 asks Jev; mode 3 buys near-misses mechanically. Consequently, “Jev makes the buy calls” is only true for one entry path. Those extra purchases can drive performance without demonstrating that the new prompt understands their setups.

The eight-week state is another gap: `backtest.py:253-260` tracks a fast-gain hold, but it is not included in the exit request and does not suppress the MA50/Jev-exit branch. With no profit target, its target-suppression effect does not supply an eight-week holding policy. Simply teaching the model an eight-week exception cannot repair a missing state or override a forced code deadline. Establish the intended exception/stop precedence in the policy; do not casually loosen protection.

Required: document which decisions are mechanical, which are delegated, and which facts govern exceptions. Run comparisons with all entry paths and configuration fields fixed and explicitly recorded.

### P2 — Entry evidence discards important distinctions

The entry serializer supplies 16 weekly OHLC bars and weekly averages of daily relative volume. It does not include the current day's volume ratio separately. The audit changes that ratio from 1.4 to 3.0 with fixed weekly evidence and obtains identical requests. Both values can coexist with the same weekly average through different earlier daily volumes.

The final bar is only described as possibly partial; the number of elapsed sessions is not supplied. A mean daily relative-volume ratio is also not conventional total weekly volume versus a weekly-volume baseline. Neither representation is inherently wrong, but the rubric must match what the numbers mean. Sixteen weeks cannot establish all longer bases, prior advances or base-stage history. Jev is text-only and is being asked to infer geometry from numbers, not actually inspect a chart.

Required: carry explicit daily breakout evidence, elapsed sessions and precomputed geometry. Longer context should be targeted to a specific missing requirement, not added indiscriminately.

## 3. What the existing evidence does and does not establish

At the audit snapshot, the cache contained **199 requests matching the new entry question set: 197 buy, 2 skip**; and **186 matching exit requests: 104 hold, 82 sell**. These are unique cached requests across runs, not an independent sample or a single portfolio ledger. The entry population is prefiltered. High acceptance does not prove either competence or failure; hard negatives and independent labels are missing.

All six tests in `src/test_timing.py` passed. They test software boundaries, not the actual model's classification of O'Neil examples. No new paid inference was performed. The synthetic checks demonstrate representation loss and validation behavior, not model accuracy. Do not attach a fabricated accuracy percentage or numeric quality grade to this setup.

Reproduce: `.venv/bin/python .lavish/audit_oneil_prompt.py`, then `.venv/bin/python src/test_timing.py`.

Reviewed source SHA256:

- `src/jev.py`: `861187d201872359dd662d21fc0575fe5a787d95168c07756536445e0f1081b4`
- `src/strategy.py`: `3dd03bd20c00fe14e0d0136ce0d22001442b9c760d8e103dfea2d679ecbfe8fa`
- `src/backtest.py`: `a9689da94e0667f47b75efb67d53091f0c4a0505f27453b376e8e9f77ddfb46d`

## 4. The evaluation needed to answer the user's question

### A. Policy fidelity before return optimization

Create a source-linked rule table. Each row names a doctrine, chosen operational definition, source/version, required evidence, code/model owner, missing-data behavior, exception precedence, and conformance examples. Freeze the intended subset. Do not use favorable historical returns to decide what counts as an O'Neil-compliant example.

### B. A contrastive comprehension exam

Build a small development set and a separate locked test set, expanding until per-category estimates are useful. Include clear valid patterns, near-valid hard negatives, mixtures and missing evidence. Example pairs:

- Same otherwise valid structure, but mature versus insufficient duration under the selected pattern rule.
- Same base, but within versus outside the declared buy zone.
- Same MA50 breach, but closes near lows on selling volume versus an intraday undercut that closes near highs.
- Good-looking structure but absent required history: insufficient evidence, not invented certainty.
- Same stock facts with an irrelevant wording or scale change: interpretation should remain consistent.
- Fast-gain exception active versus inactive: action mapping follows explicit precedence without overriding hard protection.

Labels should be derived from the scoped rulebook and independently reviewed by a knowledgeable human; disagreements must be adjudicated or retained as ambiguous. CC must not be sole policy author, sole labeler and sole judge. Do not label a base “good” just because the stock later rallied.

### C. Compare teaching methods on the same cases

Compare the old generic prompt, the current rewrite, and a source-grounded narrow rubric. Compare raw bars with precomputed evidence, and test with/without a small curated set of contrastive examples. Keep model version, cases and downstream mechanical policy fixed. Change one factor at a time; keep the final test labels away from prompt iteration.

Report per-class errors and coverage, confusion matrices, ordinal ranking agreement where appropriate, sensitivity to decisive feature changes, missing-evidence handling, and confidence-versus-correctness. Predeclare the acceptable error rates according to each action's consequences; a small pilot does not establish production reliability. Mechanical risk constraints require deterministic tests, not probabilistic assurances.

### D. Only then measure investment value

Evaluate recognition agreement, future-outcome prediction and whole-portfolio decision value separately. Backtest under the same inputs, costs, risk limits and candidate paths, then validate on genuinely new observations. The well-examined 2022–2026 sample remains development evidence even if a new prompt is called frozen.

## Recommendation to CC

Do not add more O'Neil prose and rerun until the return looks better. First fix the Score contract and evidence gaps, write the supported doctrine and its exceptions explicitly, then build the conformance exam. Better wording is a legitimate intervention; whether it actually teaches the desired distinctions is an empirical question that the current tests never ask.
