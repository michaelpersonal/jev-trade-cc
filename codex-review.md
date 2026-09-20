# Approved review handoff to Claude Code

The user approved the findings and recommendations below, then explicitly
asked Codex to share the review with Claude Code and let Claude Code implement.
Claude Code is the implementation owner. Codex has not changed strategy code.

Read this alongside `help-me-design.md`. Where the brief disagrees with the
verified evidence below, investigate and correct the brief rather than treating
its statements as established facts.

Full review: `.lavish/jev-decision-boundaries.html`

Read-only reproducible audit:

```sh
.venv/bin/python .lavish/audit_jev_boundary.py
```

The audit performs no API calls or data writes. It prints dataset counts,
source hashes, and a synthetic demonstration of the timing bug.

## 1. The decision boundary

- The user owns the research objective and risk constraints.
- Claude Code owns research design: translating the strategy into rules,
  choosing data and representations, specifying labels, establishing baselines,
  writing prompts, implementing the simulator, and interpreting evidence.
- Deterministic runtime code owns timestamps, exact calculations, eligibility,
  portfolio accounting, sizing, stops, order placement and fills, fallback
  behavior, and audit logs.
- Jev owns a narrow, explicit interpretation or forecast over the evidence
  supplied to it. Its output does not automatically earn authority over risk.

The statement in `src/jev.py` that the coded work contains no judgment calls is
incorrect. Universe selection, two YELLOW slots, the 50-day exit, thresholds,
input selection and prompt wording are all research choices. Deterministic
execution does not validate the choices.

If Claude supplies a fresh interpretation for each historical event, Claude is
also a runtime model. Freeze and evaluate its prompt, version and inputs, and
attribute its contribution separately. Do not insert historical knowledge of
famous winners into state, labels or policy design.

## 2. Repair measurement before drawing new model conclusions

### Confirmed baseline lookahead

`src/backtest.py:89–119` reads today's position limit from today's closing
market regime, then uses that limit to fill yesterday's orders at today's open.
The audit changes only the later index close and changes the earlier buy count
from one to zero. That violates the stated timing contract.

Correct the decision-time boundary and add a regression check demonstrating
that changing information unavailable at the open cannot change an open fill.
Preserve close-t signals / next-open discretionary execution and standing stops.
Recompute affected existing results; the effect on headline performance is
currently unmeasured, not assumed positive or negative.

The optional chandelier branch also uses today's ATR to construct today's
intraday standing stop (`src/backtest.py:152–157`). ATR includes today's range.
Use information available when the standing order was established. This branch
is inactive in the shipped percentage-trailing baseline.

### Historical universe and reference population

`src/strategy.py:121–133` computes RS ranks over the entire panel of ever-selected
names, then the backtest applies historical membership afterward. Knowledge of
future membership therefore affects the reference population. Make the ranking
population consistent with the information and universe available at that time.
Audit group ranking/attachment under the same principle.

Quarterly snapshots are a sampled historical universe, not exact daily
membership. Keep that limitation explicit. Investigate symbol/entity mappings
and missing histories; do not call all 49 missing symbols verified delistings
or claim their impact is known to be small. A wider universe was previously
declined; the review does not authorize silently widening it.

### Exit claim is unsupported

`data/result.json` contains 43 SELL rows whose reason starts with
`broke 50dma`. They average +5.325116% and total +$45,062.45 realized P&L.
The brief's approximately-breakeven characterization is not supported by the
saved result.

Even a zero average return would not establish that an exit rule costs money.
Compare selling with a specified continuation from the same trigger state.
Returns since original entry do not measure the incremental value of exiting.
Codex retracts its earlier recommendation to immediately move Jev to exits on
the strength of that alleged defect.

### Other measurement and description issues

- The walk-forward harness carries equity but resets positions at fold
  boundaries. Specify and implement the intended carry or liquidation policy,
  including costs, and describe exactly what the stitched record measures.
- `src/metrics.py` labels CAGR / annualized volatility as Sharpe. Correct the
  metric or its name and disclose the return/risk-free convention.
- `BASE_MIN` excludes recent crossings; it does not directly impose the
  claimed minimum base age. In the judged set, 275 rows have computed
  `base_len_wk < 5`. Reconcile the implementation and description; do not
  quietly turn a description fix into a new tuned strategy.
- Preserve old outputs as identifiable pre-repair results before regenerating
  affected reports. Distinguish measurement repairs from new trading hypotheses.

## 3. Make Jev experiments reproducible

`src/jev.py:124–143` hashes version/kind/state, but not question content or model
identity. A prompt change can silently reuse old answers unless the global
version is bumped. The client does not pin the model in code; the SDK defaults
to `jev-latest` unless configuration overrides it. The cache omits resolved
model ID, canonical request and full Score/Choice distributions.

Persist and identify:

- Exact questions, criteria and input state.
- Pinned model ID and resolved response model ID.
- Full typed responses and distributions.
- Input/preprocessing version, source hashes and decision timestamps.
- Explicit fallback behavior for missing, invalid or late responses.

Make the cache key reflect the complete inference request. Preserve legacy
answers as legacy evidence; do not invent missing provenance or silently claim
they were produced with a newly pinned version.

Current TypeSafe semantics differ from the brief: Noul has a probability and
no separate confidence field. Score and Choice confidence summarize their
probability distribution. Classification confidence is not probability of a
profitable trade, and must not be used directly as a position-size multiplier.

## 4. Three distinct evaluations

1. **Interpretation:** Does Jev correctly apply a defined rubric to the supplied
   evidence? Use independent blinded labels, disagreement adjudication, relevant
   precision/recall or ordinal agreement, and abstention/coverage measurements.
2. **Prediction:** Does its answer predict a precisely specified future outcome?
   Freeze horizon, event/barrier definitions, censoring and population. Evaluate
   probability accuracy/calibration against a training-only base rate and simple
   numerical baselines using the same information.
3. **Decision value:** Does a fixed policy using its judgment improve results
   relative to the otherwise identical policy without it? Include costs,
   drawdown, exposure, turnover, tail losses and displaced opportunities.

The existing prompts mix these targets. `proper_base` is recognition;
`quality` mixes aesthetics with an implied advance; `follow_through` is an
underspecified forecast. Pooled 20/60-day return correlations do not isolate
all three claims. The scripts that produced those correlations are absent
from `src/`; make future evaluations reproducible.

Keep the pre-agreed split-half robustness requirement, but do not mistake it
for independence. The whole 2022–2026 period has already influenced structural
choices. A newly designated historical holdout does not erase that exposure.
Walk-forward remains exploratory where the design already used the test period.
Strong confirmation requires actually unexamined observations or a frozen
prospective paper record. Purge overlapping outcome windows at fold boundaries
and account for dependence between nearby events and repeated issuer episodes.

## 5. Data and opportunity audit

Verified against local files on 2026-09-20:

| Item | Finding |
|---|---|
| Daily price panel | 865,127 rows; 586 tickers; 2020-09-01 through 2026-09-18 |
| Universe | 635 tickers in 20 quarterly snapshots; 49 lack panel prices |
| Jev evaluations | 635 events in each framing, across 361 tickers and 394 dates |
| Membership | 547 evaluated events are snapshot members; 88 are not |
| Current eligible population | 283 pass membership, buyable flag and non-RED regime; actual book constraints can reduce this further |
| Full forward outcomes | 633 have a complete 20-session close; 614 have a complete 60-session close |
| Weekly representation | 498 events fall on non-Friday dates; newest weekly bar is generally partial and lacks an explicit completeness flag |
| Ranking bottleneck | Only 12 saved baseline days have more candidates than open slots |
| Discretionary exit sample | 43 baseline 50-day exits |

Repeated questions and two framings are not additional independent market
observations. If broad screening is intentional, label the broader population
and separately evaluate the actual decision population.

The weekly builder correctly truncates daily bars before resampling. Its issue
is information loss/ambiguity, not future bars leaking through that resampling.
The summary prompt also leads with an asserted consolidation breakout before
asking whether the base is genuine. Make state factual and neutral; do not
encode the answer in the description.

Available: price/volume, index and macro proxies, indicators, sampled membership,
group data and positions/trades. Exit-specific features can be derived.

Absent: independent chart labels; original timestamped earnings releases,
filing passages, transcripts or news; reported fundamentals with original
publication/restatement versions; prior guidance; historical analyst consensus;
publication-dated sponsorship and relevant share/float histories. Jev cannot
infer these missing facts from price bars.

## 6. The next Jev contract

The review recommends semantic interpretation as the more natural documented
fit, while recognizing that price-only forecasting can be tested with the
existing dataset. The user approved the review but did not choose between
these two research directions. They redirected implementation to Claude Code
before answering Codex's optional choice question. Do not report either choice
as an explicit user selection.

### Semantic example: guidance withdrawal

Code retrieves a short original disclosure passage, relevant prior guidance
for the same period where needed, and validates public availability. It handles
period alignment and arithmetic. Jev answers whether the supplied text explicitly
states that previously issued guidance no longer applies. Optionally ground the
answer by selecting a supporting passage from a finite candidate list that
includes no support.

First validate against independently adjudicated source labels. Only afterward
test whether the feature helps a frozen policy. Correctly identifying a
withdrawal does not establish that selling helps; the price may reflect it.
This requires constructing a corpus, not merely changing the prompt.

EDGAR can supply filing history and XBRL in principle. Historical use needs
original versions, stable company identifiers, public availability timestamps
and careful treatment of later restatements. A current value for an old fiscal
period is not automatically point-in-time data.

### Price-only example: defined recovery at an exit trigger

Use a held position that first qualifies for the repaired 50-day discretionary
exit and survives that day's standing stops. Supply computed recent daily
returns, ranges and volume ratios; distances/slopes of averages; breach
depth/persistence; market/peer-relative behavior; entry, peak and active stop
distances. Mark partial weekly bars if included.

An illustrative label is recovery to a frozen decision-day MA50 within ten
sessions before touching a frozen protective stop, with same-bar ambiguity
resolved stop-first, no recovery by deadline classified as no, and incomplete
future horizons censored. These are examples, not a registered or optimized
contract. Freeze a contract before testing it.

Compare Jev against a base rate and a simple numerical predictor. If it earns
an actionable signal, test one bounded deferral of the discretionary exit with
hard/trailing protection retained. Fix the deferral deadline, fallback and
execution policy, and evaluate complete portfolios as well as paired event
outcomes. Recovery probability alone is not the payoff distribution.

## 7. Implementation order and reporting

1. Verify and fix measurement defects with focused regression tests.
2. Make model requests, caching, provenance and evaluation contracts explicit.
3. Recompute affected existing baselines/comparisons under the repaired engine
   and reconcile README, design brief, exported data and replay labels.
4. Prepare one narrow Jev evaluation with the necessary evidence and labels.
   Avoid more entry-prompt searches on the already-used pool, confidence sizing,
   or assuming exit improvement before measuring it.
5. Report changes, checks, corrected results, outstanding data gaps and the
   exact claim that any completed evaluation supports.

The current rule backtest should not be called Jev trading: Jev made none of
those portfolio decisions. Relabel local artifacts honestly. External publishing
or updating the already-published artifact is separate from local implementation.
No instruction here is to place live trades.

Removing ticker/date reduces recall contamination but is not proof of its
absence: recognizable sequences, turnover or text can still identify episodes.
Identity-guessing tests are diagnostic, not a certificate. Keep this limitation
and researcher hindsight explicit.

## Sources

- https://docs.typesafe.ai/concepts/state
- https://docs.typesafe.ai/model-jaggedness/jev-1.13
- https://docs.typesafe.ai/confidence
- https://docs.typesafe.ai/primitives/noul
- https://docs.typesafe.ai/primitives/score
- https://docs.typesafe.ai/models
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
