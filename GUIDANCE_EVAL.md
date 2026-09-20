# Jev on guidance withdrawal — interpretation evaluation

Evaluation 1 of the three in `codex-review.md` §4: **does Jev correctly apply a
defined rubric to supplied evidence?** Not whether it predicts returns, and not
whether trading on it helps. Those are evaluations 2 and 3 and are NOT done.

## Setup

129 passages from original 8-K filings, 2022-01 to 2026-09, 113 distinct
issuers (max 6 from any one). Every passage carries the `acceptanceDateTime`
from EDGAR's submissions API — the moment it became public.

Three populations, chosen so the task is not trivial:

| Population | n | What it is |
|---|---|---|
| `withdrawal` | 61 | Guidance withdrawn or suspended |
| `non_reliance` | 38 | Prior **financial statements** unreliable — the distractor |
| `guidance_move` | 30 | Guidance reaffirmed / raised / lowered — it still stands |

Rubric frozen in `src/rubric.md` before any label or Jev answer existed.

**Labels are model-generated, not human-adjudicated.** Labeller A is a regex
(`src/label_lexicon.py`); labeller B is Claude applying the rubric blind to
population and search query. They agree 89.9%, Cohen's κ = 0.792; all 13
disagreements are recorded with reasons. Gold = labeller B. This is
inter-annotator agreement between two models, not ground truth.

Jev saw the passage and nothing else — no ticker, no date, no hint of which
query found it, no framing that asserts the answer.

## Result

| Method | Precision | Recall | F1 | κ vs gold |
|---|---|---|---|---|
| **Jev** (`noul` ≥ 0.5) | 0.887 | 0.979 | **0.931** | **0.886** |
| Jev (`choice` = withdrawn) | 0.857 | 1.000 | 0.923 | — |
| Baseline: regex lexicon | 0.807 | 0.958 | 0.876 | 0.792 |
| Baseline: which query found it | 0.787 | 1.000 | 0.881 | — |
| Baseline: always yes | 0.372 | 1.000 | 0.542 | — |

**Jev beats the regex, but not significantly at this sample size.** McNemar
exact two-sided p = 0.070 (Jev right/regex wrong on 7, the reverse on 1). The
direction is consistent; n = 129 is too small to call it.

### It separates the distractor perfectly

All **38/38** non-reliance passages → `financials_not_reliable`. **Zero** were
called guidance withdrawal. All 30/30 guidance-move passages correct too. Every
one of its 7 errors is inside the `withdrawal` population (88.5% correct).

### Calibration is the real finding

| `noul` band | n | mean p | actual rate |
|---|---|---|---|
| ≤ 0.1 | 69 | 0.047 | **0.000** |
| 0.1–0.3 | 6 | 0.155 | 0.000 |
| 0.3–0.5 | 2 | 0.480 | 0.500 |
| 0.5–0.7 | 7 | 0.607 | 0.429 |
| 0.7–0.9 | 3 | 0.743 | 0.667 |
| > 0.9 | 42 | 0.976 | **1.000** |

Brier 0.0271 against 0.2336 for predicting the base rate. 86% of judgments
land outside [0.1, 0.9] — it commits rather than hedging.

**Errors concentrate exactly where it says it is unsure.** Abstaining gives:

| Abstain band | Coverage | Accuracy | Errors |
|---|---|---|---|
| none | 99.2% | 95.3% | 6 |
| [0.4, 0.6] | 95.3% | 97.6% | 3 |
| [0.3, 0.7] | 92.2% | 99.2% | 1 |
| **[0.2, 0.8]** | **89.9%** | **100%** | **0** |

Every disputed case sits between 0.46 and 0.74 — the slide-footnote currency
disclaimers, a non-GAAP reconciliation disclaimer, a company declining to
reaffirm one sub-measure while issuing full guidance, and an operating-metric
suspension. Several are ones the rubric itself flags as borderline, so calling
them Jev errors is generous to the gold label.

Cost: 129 judgments, three questions each, in seconds, for under a cent.

## What this does NOT establish

- **That trading on it works.** Correctly identifying a withdrawal says nothing
  about whether selling helps; the price may already reflect it. That is
  evaluation 3 and has not been run.
- **That the labels are correct.** Two models agreeing is not a human expert.
- **That it beats a regex.** p = 0.070. Direction yes, significance no.
- **That this generalises.** One phrase family, one form type, 2022-2026,
  English, US issuers. Passages were found by keyword search, so the corpus is
  not a random sample of filings.

---

# Evaluation 3 — decision value

Contract frozen in `src/policy_contract.md` before any post-event return was
computed. Executed exactly as written by `src/eval_decision.py`.

## Verdict: FAILS the pre-registered decision rule

The rule required Jev's signal to beat the all-events base rate **and** fall
outside the central 95% of a random signal firing at the same rate, **at two or
more horizons**. It is outside at **zero of three**.

93 tradeable events, 78 issuers, 35 gold positives. Entry is the first session
open strictly after the filing was public (median lag 1 calendar day), so the
announcement move is forgone by design. Excess return over SPY, 10 bp cost.

| Signal | n | 1 session | 5 sessions | 20 sessions |
|---|---|---|---|---|
| **Jev `noul` ≥ 0.80** | 30 | −1.18% ±2.76 | −0.63% ±4.51 | −0.73% ±6.13 |
| Gold label (ceiling) | 35 | −1.47% ±2.42 | −0.57% ±3.89 | +0.57% ±5.38 |
| Regex lexicon | 43 | −0.87% ±2.08 | +0.07% ±3.78 | +1.21% ±5.66 |
| All events (base rate) | 93 | −0.27% ±1.55 | +3.35% ±6.88 | +4.69% ±9.36 |

Every interval spans zero by a wide margin. Against the null:

| Horizon | Observed | Null 95% | Percentile | |
|---|---|---|---|---|
| 1 | −1.18% | [−2.33%, +2.11%] | 22 | inside |
| 5 | −0.63% | [−3.28%, +12.81%] | 25 | inside |
| 20 | −0.73% | [−4.77%, +18.41%] | 24 | inside |

**Even the gold label — perfect interpretation — produces nothing.** That is
the cleanest statement of the result: the failure is not Jev's reading of the
filing. Within the withdrawal population itself, raw excess returns are
−0.22% / +0.55% / +0.97%. The news is in the price by the next open.

Codex predicted exactly this: *"Correctly identifying a withdrawal does not
establish that selling helps; the price may reflect it."* It does.

## Tail behaviour of a short on the signal

| Horizon | Mean | Median | Win rate | Worst | Best |
|---|---|---|---|---|---|
| 1 | +1.18% | +1.57% | 60.0% | **−17.68%** | +19.47% |
| 5 | +0.63% | +1.42% | 53.3% | **−45.62%** | +20.66% |
| 20 | +0.73% | +2.65% | 56.7% | **−55.97%** | +34.15% |

Median above mean at every horizon: a positive-looking median financed by
catastrophic left tails. A −56% single-event loss on 30 events would dominate
any portfolio built this way. No borrow cost is modelled, which flatters the
short further.

## One post-hoc check, reported because it is also null

The base rate is distorted by the non-reliance population (micro-cap
restatements, +13.95% mean excess at 5 sessions) which inflates the null's
upper tail. Dropping it — **not part of the frozen contract** — leaves the
conclusion unchanged: inside the null at all three horizons.

| Horizon | Jev | All | Null 95% | |
|---|---|---|---|---|
| 1 | −1.18% | −0.52% | [−2.32%, +1.28%] | inside |
| 5 | −0.63% | +0.29% | [−2.84%, +3.38%] | inside |
| 20 | −0.73% | +2.47% | [−3.10%, +8.20%] | inside |

## Limitations, stated rather than corrected

- **n = 93**, from 129 corpus passages: 32 lost to unresolved tickers, 4 to
  missing prices. Of the 14 unresolved withdrawals, **6 mention an acquisition
  or merger** — deal-pinned prices do not fall, so dropping them biases the
  test *toward* finding a negative drift. It still found none.
- **Events are not independent.** 15 share an issuer, and 73% of consecutive
  events fall closer together than the 20-session window, so those windows
  overlap. Intervals are narrower than they should be.
- **The corpus was built by keyword search**, so it is not a random sample of
  filings.
- No borrow cost, no market impact, no short availability constraint.

## Where the three evaluations leave it

| | Result |
|---|---|
| 1. Interpretation | **Jev works.** F1 0.931, perfect on the distractor, calibrated well enough that abstaining below 0.8 gives 100% accuracy at 90% coverage. |
| 2. Prediction | Not run as a separate test; subsumed below. |
| 3. Decision value | **No.** Fails the pre-registered rule at every horizon, and the gold label fails too. |

Reading a filing correctly and profiting from it are different problems. Jev
does the first one well. The second is not available here — not because the
model is weak, but because the market had already read the filing.
