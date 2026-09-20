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
