# Re-review: fixes accepted, strategy-quality claim still unproven

Reviewed through `a718ea2`, including `923af12` and `e003da7`. Production worktree was clean. This is review feedback, not an implementation or a new performance experiment. No paid model calls were made.

## What is fixed

- `src/jev.py:250`: the moving-average stack is now measured from the row instead of asserted universally. This fixes the broad-pool false-evidence defect. Missing slope values still deserve an explicit unknown state rather than Boolean coercion.
- `src/jev.py:436`: routine holding review is parameterized, not repaired with a failing string replacement. A healthy synthetic holding now receives the routine-review opening.
- `src/jev_select.py:81`: accepted setup labels derive from the actual question. `faulty` is accepted; the current assessment artifact contains 22,398 rows, including 10,704 faulty and 195 valid setups. That fixes the old missing-faulty artifact. Failure counts are now printed.
- `src/backtest.py:542`: selection and mechanical near-miss purchases are mutually exclusive. The synthetic all-none selection now produces zero buys despite near-miss candidates.
- `src/exam_oneil.py:92`: stable integer seeds replace process-salted hashes. Two processes with different PYTHONHASHSEED values now generate the same serialized case hash.
- `src/compare.py`: the previously external shipped configuration and assessment loading now have a committed runner. This is a meaningful reproducibility improvement.

All six timing/integration guards pass. Seven targeted mutations are caught: open-fill close lookahead, contemporaneous ATR, missing evidence provider, stale weekly cache, omitted lookback cache key, unlimited mode-1 deferral, and unexpected-label acceptance. The ATR guard includes a source-text check; this is not comprehensive execution coverage.

## Remaining findings, ordered by conclusion impact

### 1. The exam still cannot establish O'Neil comprehension

**Files:** `src/exam_oneil.py:45`, `src/exam_oneil.py:54`, `src/run_exam.py:9`.

Stable seeds fix reproducibility, not construction validity. The extension bad arm draws fresh noise for the entire price path, so all 16 OHLC bars change. The advance pair also changes the entire price history, and now explicitly changes the trend-template verdict. These are not otherwise-identical pairs differing only in the named dimension.

The hardcoded pivot is not derived from the generated highs. For the actual extension good-arm seeds 1000, 1001 and 1002, final closes are 101.139, 101.920 and 101.320, while preceding highs are 102.082, 102.036 and 102.472. These examples do not establish their advertised breakout above the prior high. A chart-specific handle pivot would need to be identified and checked, not assumed to equal 100. The generated 52-week high also uses closes rather than the supplied intrabar highs.

Most importantly, the new runner calls **decide_entry / ENTRY_DECISION**, not **ASSESS**, **select_question**, or **HOLDING_REVIEW**. It now reports old entry-policy acceptance as well as pair rankings, which is useful, but it does not test the newly instituted strategy prompts.

**Invalidates:** treating the exam as proof that the current selector understands O'Neil. It remains a directional test of the older entry questions on imperfect synthetic fixtures.

**Required correction:** fix fixture invariants before another paid run; reuse unchanged noise; derive indicators from coherent price histories; assert intended pivots and buy-zone boundaries; test the current questions directly. Include valid, faulty, developing, extended and insufficient cases, not only relative good/bad scores. Record the exact generated cases and request fingerprints.

### 2. The detailed strategy does not reach the final selection call

**Files:** `src/jev.py:593`, `src/backtest.py:495`.

The selection instruction still amounts to “following William O'Neil … choose one or none.” A stateless call does not inherit ASSESS's detailed instructions. Its options contain RS, extension, depth, volume and two numbers, but no recognized pattern, pattern-specific pivot, base timing, or explicit comparison policy.

Worse, Phase A asks Jev to identify the actual pattern's buy point, but Phase B substitutes the rolling 65-session pivot and depth, describing them as the base. The inferred pattern and its anchor never survive Phase A. The supply probability is labeled “supply dried up,” although its question jointly tests contraction and breakout expansion; these numbers are not measured magnitudes of either property.

**Invalidates:** the claim that improving ASSESS alone institutes O'Neil's stock-selection process from top to bottom.

**Required correction:** make selection self-contained. Carry pattern identity, verifiable anchors, observed supporting facts and uncertainty forward; define what should make one eligible setup preferable to another and when none is appropriate. Do not replace Jev's choice with a hidden weighted score. Code can calculate distances and durations from Jev-selected anchors without taking over pattern recognition or the final choice.

### 3. Assessment data still lacks a verifiable contract

**Files:** `src/jev_select.py:103`, `src/backtest.py:65`, `src/backtest.py:418`.

The current full artifact's row count is encouraging, but its records carry no prompt/model/data fingerprint or per-request failure status. Console counts do not travel with the parquet. Changing a prompt while keeping an older parquet is not rejected. A limited run without --sample still overwrites the production artifact. An absent/empty assessment mapping with JEV_SELECT enabled produces zero buys, zero calls and zero errors in the synthetic reproduction.

**Invalidates:** interpreting every zero-candidate day as a model decision, or assuming a run uses the current criteria merely because its code does.

**Required correction:** validate an assessment manifest, requested-universe coverage and compatible fingerprints before selection. Persist unknown/error/no-history separately from an assessed negative. Partial runs must not masquerade as complete datasets.

### 4. Exit-mode switches and original-base evidence remain inconsistent

**Files:** `src/backtest.py:301`, `src/backtest.py:358`, `src/backtest.py:610`, `src/jev.py:427`.

Reproduction: mode 2 with JEV_EXIT=False still calls routine review. Mode 0 with JEV_EXIT=True still calls the legacy override. Returned config omits JEV_EXIT_MODE, JEV_SELECT and REVIEW_EVERY. Thus neither switches nor result metadata reliably identify the executed policy.

Both exit paths pass today's rolling pivot to text claiming it is the top of the base the position broke out of. That reference changes as new highs enter the window; it is not the original entry base. Persist the entry setup anchor separately.

Mode-2 unclear answers held a below-MA position through 23 reviews, with zero errors and no expiry in the synthetic fixture. That can be an intentional autonomous policy, but it is not the bounded mode-1 contract. Define and version its abstention/error behavior explicitly; a mandatory ten-day cap is not inherently required for an autonomous selector. Also record abstention distinctly from a confident hold.

### 5. The new survivorship analysis overstates its statistical conclusion

**Files:** `SURVIVORSHIP.md` section “How big is it”; `src/jackknife.py` final interval print.

Identifying missing point-in-time constituents is important. But removing additional observed names measures sensitivity to that deletion procedure. Multiplying the resulting equity standard deviation by 1.96 does not establish a confidence interval for the unknown missing-data bias. The observed survivors are not interchangeable with the missing securities, and the real missingness mechanism has not been identified by this experiment.

Nor can rules-only equity dispersion be compared directly with Jev's incremental effect to conclude that the effect is smaller than its measurement noise. Estimate **Jev equity minus rules equity within each identical draw**; common changes may cancel or amplify. The paired difference's dispersion is the relevant sensitivity statistic.

Scheme B uses first-snapshot minus last-snapshot membership. It excludes stocks that entered and subsequently left between those snapshots, and exit membership is not itself the same process as missing vendor history. The missing-name list also includes a duplicate NLOK and possible symbol changes; audit security identities before calling every missing ticker a delisting with irrecoverable prices.

**Required correction:** retain the sensitivity warning, withdraw the confidence-interval interpretation and unmeasured signal-to-noise comparison. Treat bias direction as a hypothesis, not a quantified correction. This does not establish that Jev works or fails.

## Criteria fidelity: better outline, not yet a tested strategy specification

Using explicit instructions is appropriate for a stateless fixed-weight model. The problem is not “strategy in a prompt”; it is an incomplete specification, sometimes mismatched evidence, and insufficient conformance testing.

- **Supported outline:** prior advance, base duration/depth, handle location, breakout volume and avoiding extended entries are recognizable O'Neil concepts. Primary IBD materials support the general structure. Published summaries differ in typical depth ranges; choose and cite a version rather than treating every approximation as an absolute universal rule. [IBD buying guide](https://get.investors.com/wp-content/uploads/2024/08/IBDD-How-to-buy-Stocks-infographic.pdf), [O'Neil/IBD flat-base booklet](https://shop.investors.com/images/promotional/flat-b-b_112408.pdf).
- **Missing rule:** ONEIL_RULES specifies the double bottom's second low undercutting the first; ASSESS omits it. Cup shape quality and exception treatment also need an explicit scope, not reliance on the strategy's name.
- **Policy disguised as fidelity:** ASSESS turns later-stage bases into categorical faulty setups, while ONEIL_RULES merely says they fail more often. Sixteen weekly bars generally cannot establish a multi-base history. Unknown base count must not become inferred certainty.
- **Overlapping labels:** an extended but immature or faulty pattern fits multiple options. Specify precedence, or separate pattern validity, entry readiness and evidence sufficiency. ASSESS uses Choice, so the older Score-neighbor defect is not the applicable criticism here. [TypeSafe Choice contract](https://docs.typesafe.ai/primitives/choice).
- **Volume mismatch:** the prompt asks about weekly volume versus its own average, while weekly evidence aggregates daily relative-volume values. That is not the same statistic. Supply contraction and breakout expansion need precisely identified measurements, including whether the current week is partial.
- **Exit scope:** HOLDING_REVIEW describes trend deterioration, not the entire O'Neil selling method. Profit-taking into strength, exceptions and the precedence of the eight-week rule versus deterioration need a deliberate specification. Do not claim the full sell discipline merely because the prompt mentions O'Neil.
- **Document correction:** protective stops should be referenced to purchase price/cost, not the buy-point price as ONEIL_RULES currently says. Do not change the currently cost-based implementation to match that mistaken sentence. [IBD 20 rules](https://shop.investors.com/images/promotional/20-Rules_102808.pdf).

The 13-week-high eligibility event, alphabetic cap, one-purchase-per-day selection and five-session review cadence are explicit policy restrictions, not necessarily programming defects. They constrain what Jev can do and should be named in the strategy definition. A 13-week high is not universally the correct pivot even for a shorter flat base. C/A/I omission means this is a technical subset, not full CAN SLIM.

The combined arm now explicitly calls itself “selects, filters and exits.” Its extra legacy entry gate is therefore an intentional hybrid comparison, not automatically a concealed bug. It still should not be described as unrestricted Jev selection. The four arms also change candidate supply when selection disables near-miss purchases, so their difference is a whole-policy difference, not a pure test of comparative ranking skill.

## Verification and limits

Offline reproductions: `.venv/bin/python .lavish/review_request_audit.py` and `.venv/bin/python .lavish/review_guard_mutations.py`; regression suite: `.venv/bin/python src/test_timing.py`. The older audit's FAULTY_LABEL_PROBE intentionally uses the obsolete hardcoded set and is not a current-loader regression; separately checking the new derived set accepts faulty.

I did not rerun the paid four-arm comparison or the 40 deletion experiments, certify a particular edition of the complete book, or independently establish the claimed $55,000 prompt-only effect. Earlier frozen experiments do not validate these newly changed prompts. Freeze the corrected evidence/schema/policy and conformance tests before treating further return changes as improvements in Jev's strategy skill.
