# Review request: are these O'Neil criteria faithful, and is the harness sound?

You are reviewing a backtest in which **Jev** — TypeSafe's System One model —
selects the stocks. Repo: `~/projects/jev-trade-cc`
(public at github.com/michaelpersonal/jev-trade-cc).

Do not optimise returns. The question is whether this system faithfully
implements William O'Neil's method and measures itself honestly. A finding that
it does not is the useful outcome.

## What to know before reading code

Jev has fixed weights, cannot be fine-tuned, and does not learn between calls.
Every call is stateless. **All of its specialisation comes from prose I wrote**
in `src/jev.py` — the `instructions` and `criteria` of each question. Changing
only that prose has moved the backtest result by roughly $55,000 across this
project with the model, data, stops and sizing held constant. So the criteria
are the strategy, and they are the primary object of this review.

## The specific things I need checked

### 1. Are the criteria faithful to O'Neil?

`ONEIL_RULES.md` lists the numbers I built the criteria from, with sources.
**Those are secondary sources summarising *How to Make Money in Stocks*, not
the book.** If you have the primary text, check them. In particular:

- prior uptrend ~30%; cup 12–33% deep and ≥7 weeks; flat base <15% and ≥5
  weeks; double bottom <40% and ≥7 weeks with the buy point at the middle peak;
  handle in the upper half, drifting down on light volume; breakout volume
  ≥40% above average; buy zone ≤5% above the pivot
- What is **missing** that changes outcomes? C, A and I of CAN SLIM are absent
  by design. Base counting is absent. Is anything else load-bearing?
- Read `src/jev.py` `ASSESS`. Does each option describe a situation a reader
  could identify from weekly bars alone, without reference to the other
  options? TypeSafe's Score contract states levels are evaluated separately
  and cannot see their neighbours; a previous version violated this with
  "everything above, plus…".

### 2. Is the evidence sufficient for the question asked?

A prior review found the exit question asking about "closes near the lows" and
"undercuts that recover" while the state carried neither — a day closing at its
low produced a byte-identical prompt to one closing at its high. That is fixed.
**Look for the same class of defect elsewhere.** Check `describe_shape` and
`describe_position` against every question that consumes them. Construct two
inputs that should differ and verify the serialised state actually differs.

### 3. Is code still deciding what it claims to delegate?

The stated boundary is: code owns eligibility, risk and execution; Jev chooses
among allowed actions. Verify it. Earlier versions failed this twice — five
quality thresholds cut the pool from 22 names/day to 0.3 before Jev saw it, and
a "neutral" ordering still ranked candidates by relative strength before
truncating. Current known residuals, which I want your judgement on:

- the candidate pool comes from a **13-week-high** event, so a double bottom's
  buy point (the middle peak, below that high) can never be offered
- the selection question shows at most **10 options, ordered alphabetically**;
  the cap binds on 405 of 1,092 days, so on a third of days the alphabet
  decides who is seen
- the routine holding review fires every **5 sessions**, a cadence I invented;
  O'Neil sold on evidence, not on a schedule

### 4. Is the measurement honest?

- `src/test_timing.py` — six guards. Each should fail against the defect it
  covers; two previously passed vacuously. Verify they still bite.
- Frozen contracts: `prereg_*.md`, `rubric.md`, `deferral_contract.md`,
  `policy_contract.md`. Were they honoured?
- `src/exam_oneil.py` — 48 generated paired cases, labels following from
  construction. Is the generator actually producing what it claims, and do the
  pairs differ **only** in the named dimension?
- Anything in the repo stated as established that the evidence does not carry.

## How to report

Findings ordered by how much they change a conclusion. For each: the file and
line, what is wrong, a reproduction, and what it invalidates. Separate
**defects** (the code does not do what it says) from **design disagreements**
(it does what it says and you think it should do something else).

State plainly where you could not verify something. I would rather have a short
list of confirmed problems than a long list of suspicions.

## What not to do

Do not tune parameters. Do not propose a configuration because it returns more.
Every number in this repo has been moved by a bug at least once, so treat any
result as provisional until its measurement is checked.
