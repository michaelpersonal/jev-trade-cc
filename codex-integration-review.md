# Review of the new Jev trading hooks

Reviewed 2026-09-20 against the working-tree changes to `src/backtest.py`,
`src/jev.py`, and `src/strategy.py`, based on HEAD `004c110`.

This is feedback for Claude Code to implement. Codex has not changed the
implementation. All diagnostic model responses were mocked; no API calls,
strategy sweeps, or production result writes were performed.

## Verdict

Jev now has actual entry and exit decision hooks. With correctly loaded inputs,
its answers can change the portfolio. This is real integration, but the normal
runner, failure handling, delegation limit and experiment audit trail need work
before a result from it is a defensible comparison.

Positive checks: the two existing timing tests pass; an initialized synthetic
run with all-buy entry answers and all-sell exit answers reproduces the baseline
equity exactly; a hard stop still closes the position despite Jev's earlier
hold answer. The weekly builder cuts off bars at the decision date.

## Findings, ordered by importance

### 1. [P1] Initialize the Jev input history in the actual runners

Location: `src/backtest.py:282–293`; setup in `:63–69`.

`JEV_ENTRY=True` depends on a separate `load_panel()` call, but no checked-in
caller invokes that function. Neither `backtest.py`'s main nor `run_all.py`
initializes it. `weekly_bars()` returns None and every candidate is silently
skipped before `decide_entry()` runs. Enabling the switch in the documented
workflow therefore creates an all-cash run with zero Jev entry decisions.

Reproduction: synthetic baseline buys once and sells once. With entry enabled
and the same data, it buys zero times and makes zero calls to a mocked Jev that
would always return buy. Loading the panel and clearing the weekly cache makes
the buy and Jev call occur.

Fix: make historical input an explicit run dependency or initialize it inside
the supported runner before evaluation. Treat a wholly uninitialized input
provider as a configuration error, not an ordinary rejected candidate. Add an
integration check that enables Jev through the actual supported entry point.

### 2. [P1] Enforce the bounded exit delegation in code

Location: `src/backtest.py:243–264`.

A qualifying 50-day exit asks Jev again every day. A hold answer has no expiry,
maximum deferral, or recorded start of the episode. The same exit can therefore
be vetoed for the rest of the backtest, as long as the standing stops do not
fire. This is broader authority than the bounded deferral in the approved
review. Protective price stops do not bound holding duration or capital use.

Reproduction: one position under its MA50, with lows above its protective stop,
received 13 successive hold overrides in a 15-session replay and remained open
at the end. The mechanical baseline sold it.

Fix: define a fixed deferral contract and retain episode state: initial trigger,
deadline, recovery/reset rule, and forced next-open action at expiry. Freeze the
duration before comparing returns. Supply the permitted action/duration and
active protective-stop context to Jev. Keep standing stops outside model control.

### 3. [P1] Separate inference failure from a model decision

Location: `src/backtest.py:290–296` and `:253–264`.

The entry branch swallows every exception from `decide_entry()` and treats it
as skip. A network outage, invalid request, missing input field or programming
bug becomes an apparently legitimate all-cash strategy. No error count, reason
or decision coverage is recorded in the result. The exit branch also hides
errors while silently falling back to the rule.

Validation is inconsistent: entry response indexing happens outside the try,
so an action=buy response without conviction crashes with KeyError instead of
using a deliberate fallback. Exit treats every choice other than sell as hold,
including an unexpected cached label. A mocked unexpected label produced the
same 13 exit vetoes as hold. This matters at the dict/cache boundary even if
normal live SDK responses are well-formed.

Fix: validate the complete response and require explicit allowed choices;
reject nonfinite or out-of-range values; distinguish model abstention, missing
evidence, inference failure and policy rejection. For an offline evaluation,
fail the run or explicitly mark it incomplete when required inference is
unavailable. If a live fail-closed policy is desired, record it separately so
its effects are not credited to Jev. Freeze any uncertainty/abstention policy
rather than acting on a winning label while discarding its probabilities.

### 4. [P1] Persist decisions and make results traceable to their model run

Location: `src/backtest.py:316–330`; callers `src/backtest.py:338–351` and
`src/run_all.py:33–46,120–125,149–154`.

The added output is only a total `jev_holds` count. There is no decision ledger
for skipped entries or held exits, no event-to-request-fingerprint link, and no
record of model failures, baseline actions, accepted probabilities, or enabled
Jev flags. The exported run metadata also omits those flags and the model
version. `n_cands` is overwritten after model filtering, hiding the original
opportunity count.

Additionally, `ask()` updates the cache only in memory. The existing judging
scripts explicitly call `J.save_cache()`, but the trading runners do not. New
trading answers are not guaranteed to survive process exit. An ad-hoc shell
driver may save them manually, but the repository has no reproducible supported
runner that does so.

Additional reproduction: ran the real `ask()` implementation against a fake
transport inside a synthetic trading run. It executed one buy and created one
in-memory cache record, called `save_cache()` zero times, and left the on-disk
cache unchanged. The run result contained neither a configuration record nor a
decision ledger.

Fix: persist an immutable decision record containing run ID, ticker/date on the
evaluator side, request fingerprint, baseline action, model answer/distribution,
policy action, fallback/error, and eventual order link. Save the request cache
reliably from the runner and support strict cache-only replay. Persist the full
configuration and source/data/model identities with outputs. Keep the initial
candidate count separately from accepted candidates. Verify that the second
run has no network calls and reproduces the same decisions and equity.

### 5. [P2] Invalidate weekly evidence when its underlying inputs change

Location: `src/backtest.py:63–86`.

`load_panel()` replaces `_PANEL` without clearing `_WEEKLY`, and the weekly
cache key is only `(ticker, upto)` despite the function accepting a `weeks`
argument. Cached None entries survive later initialization. Replacing a panel
in the same process returns the old data, and asking for eight weeks after
sixteen returns sixteen.

Reproduction: calling before initialization, then loading the panel, still
produced zero model calls until `_WEEKLY.clear()`. A 16-week request followed
by an 8-week request returned 16 rows both times. Replacing closes of 100 with
200 still returned 100 from the cached weekly bars.

Fix: clear/version the weekly cache on panel load, include the requested
lookback in its key, and preferably scope the evidence provider/cache to the
run. Add checks for initializing after a missing-data lookup, panel replacement,
and different lookbacks.

### 6. [P2] Give the entry ranking output a defined meaning

Location: `src/jev.py:289–291`, consumed at `src/backtest.py:296–312`.

`conviction` is a Noul, but asks “how strong is this candidate”. Noul represents
the probability of a yes/no proposition, not a degree-of-strength scale. The
answer is then sorted to decide which stocks receive the available slots. The
comparison therefore relies on an undefined scalar despite being type-correct.

Fix: use a Score with explicit ordered criteria if the task is strength rating,
or a Noul with a precisely defined binary proposition if the task is prediction.
Do not present either as calibrated investment conviction without outcome
validation. Keep the ranking change identifiable separately from the entry veto.

Source: https://docs.typesafe.ai/primitives/noul

## Additional measurement issue still present outside the new patch

`src/backtest.py:345` still calls `S.build_signals(pan)` without membership,
although `strategy.build_signals()` only applies historical eligibility when
membership is passed. `run_pipeline.sh` invokes this entry point. It can
therefore regenerate and overwrite signals with the original contaminated RS
reference population, undoing the earlier repair. Pass membership through all
production builders and test the documented end-to-end workflow. This is an
unresolved earlier repair, not a defect introduced by the Jev hooks.

Controlled reproduction with a present member and a future-only name: the
present member's RS was 50 when membership was omitted and 99 when historical
membership was passed. That can cross the existing RS>=80 entry threshold.

## Design feedback, separate from the executable bugs

- The exit prompt asks about shakeout versus breakdown but only supplies a
  point-in-time summary. It does not include the recent daily sequence,
  normalized ranges, volume evolution, MA slope, relative market/peer path,
  active stop distance or permitted deferral horizon. These are mostly
  available/derivable from existing data. Define the judgment and supply the
  evidence needed to make it; this input currently cannot distinguish many
  materially different price paths.
- The entry hook is still a veto and reranker downstream of the complete
  O'Neil screen (`rows[buyable]`). It cannot discover excluded candidates or
  increase signal supply. That is a legitimate bounded experiment, but should
  be described as “Jev filters/ranks rule-selected candidates”, not Jev choosing
  investments from the full universe.
- Use a fixed comparison of rules-only, entry-only, exit-only, and both if both
  decisions are being explored. Keep settings, data and execution identical;
  report interactions and exposure. Do not tune the configurations on the
  resulting returns. The existing `run_all.py` sweeps exit parameters and slot
  counts; simply enabling global Jev flags makes those sweeps model-assisted
  too, rather than producing the required clean component comparison.
- The guidance classifier is not used in these new entry/exit calls. Its
  interpretation accuracy does not validate these different numerical prompts.
- No requirement here is to prove profitability before running the experiment.
  The requirement is that the experiment executes the stated policy, records
  what happened, and permits a fair comparison even when the answer is a loss
  or a null.

## Verification performed

- `.venv/bin/python src/test_timing.py`: both existing tests pass; both Jev
  switches are off in that suite, so it does not exercise the new paths.
- In-memory mocked replay: baseline one buy/one sell; entry enabled without
  provider initialization zero buys/zero model calls; correctly initialized
  entry one buy/one model call.
- In-memory mocked outage: zero entries with no recorded error status.
- In-memory malformed responses: entry raises KeyError; unexpected exit action
  is interpreted as hold.
- In-memory repeated-hold replay: 13 overrides and a still-open position.
- In-memory weekly-cache checks: stale None, stale panel values and wrong
  lookback length reproduced.
- In-memory positive controls: initialized all-buy/all-sell answers reproduce
  baseline equity; a hard stop still executes following a hold answer.
- Input-cutoff check: changing only bars after an entry decision did not change
  the actual serialized state supplied for that decision, with caches reset
  between variants.
- Real request/cache path with a fake transport: an answer exists in memory
  after the trading run, but no cache persistence occurs.
- Two-symbol signal-builder check: the documented builder call can still use
  the future-selected reference population and move an RS rank from 99 to 50.

Implementation and market-data files were not modified by this review.
