# Rubric: "guidance withdrawal" — FROZEN 2026-09-20

Frozen before any Jev answers were requested and before any label was assigned.
Do not edit to accommodate results; if it proves inadequate, record that as a
finding and version it.

## The question

Given a passage from an original SEC filing, does the passage **explicitly
state that previously issued forward-looking financial guidance no longer
applies**?

## Label YES when

The passage states that company-issued projections for a future period —
revenue, EPS, margin, comparable sales, or similar — are being **withdrawn,
suspended, rescinded, or should no longer be relied upon**.

Includes:
- Withdrawal limited to one period ("withdrawing our full-year 2025 outlook").
- "No longer reaffirming" / "is not reaffirming" **only where** the passage
  makes clear the prior guidance no longer stands.
- Guidance withdrawn because of a pending acquisition, restructuring, or
  macro uncertainty. The reason is irrelevant; the effect is what is labelled.

## Label NO when

- Guidance is **reaffirmed, raised, lowered, narrowed, or updated** — it
  changed, but it still applies.
- What is withdrawn is **not forward guidance**: most importantly, a statement
  that previously issued **financial statements** should no longer be relied
  upon. That is a restatement of history, not a withdrawal of a forecast.
- The company **declines to initiate** guidance it had never issued.
- Guidance is merely mentioned, quoted, or referenced.
- Withdrawal appears only as a **hypothetical, conditional or risk-factor**
  statement ("we may be required to withdraw our guidance"), or inside
  forward-looking-statements boilerplate.

## Abstention

Label UNCLEAR when the passage is truncated at the decisive clause, or is so
ambiguous that a careful reader could defend either answer. Abstentions are
reported as coverage, not scored as errors.

## Labellers

- **A — lexicon**: deterministic regex, `src/label_lexicon.py`. Transparent and
  reproducible; deliberately simple so it is a real baseline, not a ceiling.
- **B — Claude**: applies this rubric to passage text with population and
  search query withheld.

Neither is a human securities analyst. Agreement between them is evidence the
task is well posed, not proof the labels are correct. Report Cohen's kappa and
adjudicate every disagreement explicitly.
