# Jev trading system — design brief

You are picking up a working research rig, not a blank page. Read this before
touching code.

**Revised 2026-09-20** after an external review (`codex-review.md`) found three
measurement defects and one false claim in an earlier version of this brief.
All are fixed or corrected below; every number here is post-repair. Pre-repair
outputs are preserved in `data/pre_repair/` and must not be cited.

The repo is `~/projects/jev-trade-cc` (git initialised). A sibling
`~/projects/jev-trade` is an abandoned earlier attempt — ignore it except that
its `.env` holds the API key.

---

## 1. What Jev is (read this first — the previous agent got it wrong)

**Jev is a model, not this project.** It is TypeSafe AI's "System One" model:
it returns type-safe structured values with calibrated probabilities instead of
text.

- Docs index: <https://docs.typesafe.ai/llms.txt> · HTTP API `POST /v1/systemone`
- `pip install typesafe-sdk`, auth via `TYPESAFE_API_KEY` (already in `.env`,
  gitignored)
- Claude Code skill: `claude plugin marketplace add typesafe-ai/skills` then
  `claude plugin install typesafe@typesafe-ai`
- Models `jev-latest` / `jev-1.13.0`; $0.042 per million input tokens, output
  free; 70–500 ms; 1,200 req/min
- Three primitives: `Noul` (calibrated 0–1 probability), `Score` (position on
  ordered levels), `Choice` (categorical). **`Noul` returns a probability and
  has no separate confidence field.** `Score` and `Choice` return `confidence`,
  which summarises how peaked their probability distribution is — it is *not*
  the probability that a trade will be profitable. Many questions can ride in
  one call.

```python
from typesafe_sdk import TypeSafeClient, Noul, Score, Choice
r = TypeSafeClient().system_one(state="...", questions={"k": Noul(instructions="...")})
r.answers["k"].noul          # 0.0 – 1.0
```

TypeSafe's own design guidance: **keep code in control, hand System One only
the narrow judgment calls.**

The first agent spent an entire session assuming "Jev" was a directory name and
hand-wrote a rule engine instead of using the model. The rules work and are
worth keeping — but nothing in the current trading loop is a Jev decision, and
the artifact and draft post both use "Jev" to mean the rule engine. That
naming is currently false. See decision **D4**.

---

## 2. The brief

Trade a William O'Neil momentum strategy from **2022-01-03 to 2026-09-18**
(1,182 trading days) with **$100,000**, long only, no margin. Benchmark is the
same $100,000 in the S&P 500, held.

**The hard constraint: no hindsight.** Every decision may use only information
available before that moment. This is the point of the exercise, and it is
already enforced throughout — do not weaken it.

---

## 3. What exists

```
src/universe.py    point-in-time index membership from Wikipedia revisions
src/sectors.py     point-in-time GICS classification, same method
src/data.py        daily OHLCV panel via yfinance
src/strategy.py    O'Neil rules as vectorised indicators; all params at top
src/groups.py      industry-group relative strength
src/macro.py       macro regime from traded proxies (VIX, HYG/IEF, XLY/XLU)
src/backtest.py    day-by-day simulation
src/walkforward.py walk-forward harness (18m train / 6m test / 6m step)
src/experiments.py ablation runner
src/jev.py         the Jev boundary — anonymised state, cached answers
src/jev_judge.py   entry judgments, summary-feature framing (v1)
src/jev_judge2.py  entry judgments, serialised weekly bars (v2)
src/run_all.py     driver; writes web/data.js
web/index.html     animated replay page (published artifact)
```

**Timing contract.** Signals on day `t` use bars through day `t`'s close.
Entries and trend-break exits fill at day `t+1`'s open. Stops and trailing
stops are standing orders filling intraday against day `t`'s high/low; a gap
through fills at the open. Trailing levels on day `t` are built from peaks
through day `t-1`. Universe on day `t` is the most recent Wikipedia snapshot
dated on or before `t`.

**Decision-time boundary.** Information that exists only after an order fills
must not be able to change whether it filled. `src/test_timing.py` enforces
this and is proven to fail against the original defect. Run it after any change
to the loop.

**Costs.** 5 bp slippage per side, zero commission. **Dividends are not
modelled** on either side — the benchmark `^GSPC` is a price index too, so the
comparison is roughly fair, with a small residual bias *favouring* the strategy
(buy-and-hold forgoes yield on 100% exposure, the strategy on ~55%).

**Universe.** 635 tickers were ever S&P 500 or Nasdaq-100 members in the
window; 586 have usable price history. The 49 missing have **not** been
individually verified as delistings — some may be symbol or entity-mapping
failures. Their impact is unquantified. Do not repeat the earlier claim that
it is "small". Snapshots are quarterly, so membership is a sampled historical
universe, not exact daily membership.

RS is now ranked only against names that were in the index on that date. It
previously ranked against every name that was *ever* a member, which leaked
future membership; fixing it removed 45 buy signals (398 → 353).

---

## 4. Current result

Shipped config: 5 positions, 15% trailing stop, 7% hard stop, macro and group
filters off.

| | Jev rules | O'Neil as written | S&P 500 |
|---|---|---|---|
| Final | **$124,242** | $86,897 | **$159,500** |
| Total return | +24.2% | −13.1% | +59.5% |
| CAGR | +4.7% | −2.9% | +10.4% |
| Max drawdown | **−21.2%** | −23.2% | −25.4% |
| Return ÷ volatility | 0.31 | −0.20 | 0.61 |

101 closed trades, 33.7% win rate, profit factor 1.31. Best INTC +87.8%,
worst PWR −13.3%. Exits: 39% hard stop, 49% "broke the 50-day line", 13%
trailing stop.

Note the second column: with O'Neil's fixed profit target the strategy now
**loses money**. Pre-repair it showed +4.7%.

| Period | Jev rules | S&P 500 |
|---|---|---|
| 2022-01 → 2024-03 | **+19.0%** | +9.5% |
| 2024-04 → 2026-09 | +8.1% | **+45.9%** |

The "worked then stopped working" shape survives repair but is much weaker:
first-half outperformance is 9.5 points, not 19.

---

## 5. Already ruled out — do not re-litigate without new data

Each of these cost real work. Re-running them is waste.

**O'Neil's fixed 20–25% profit target is the single most damaging rule.**
It capped NVDA at +25% seventeen days after entry; the stock went 4.5× from
that price. Replacing it with a 15% trailing stop takes the run from **−13.1%
to +24.2%** — the difference between losing money and not. Treat this as
*"don't cap winners"*, **not** as a tuned number: post-repair the full-period
sweep favours a 12–15% trail while out-of-sample favours 10%, so the exact
figure is unresolved.

**Macro overlay and industry-group RS both reduce full-period returns.**
Baseline +24.2%; every variant is lower (macro veto +3.0%, macro symmetric
+7.5%, groups top-50 +13.9%, groups top-25 +5.3%, both combined −5.0%). Both
work by cutting exposure (57% → as low as 41%). Note they *do* beat baseline in
the weak half (up to +17.1% vs +8.1%) and lose heavily in the strong half — so
the honest statement is "they trade strong-regime return for weak-regime
protection", not "they don't work". Kept in the tree, off by default.

Breakouts also *already* cluster in strong groups — 189 of 353 signals sit in
the top quartile, 24 in the bottom — so an explicit group filter mostly deletes
signals rather than improving them.

**Walk-forward parameter re-fitting loses to a fixed setting, badly.**
$84,783 vs $105,621 over seven out-of-sample folds, beating the constant in
only **1 of 7**, and choosing a different configuration in **7 of 7**. The
parameters are noise. Caveat: the harness carries equity but resets positions
flat at each fold boundary, and that liquidation is currently uncosted — the
intended carry policy needs specifying before these figures are quoted
precisely.

**Exposure is a dial, not an edge.** Sweeping the YELLOW slot count
post-repair, full-period peaks at 3 slots (+41.3%) — which is the **worst**
out-of-sample cell (+1.8%). The out-of-sample column zigzags (10.1 → 5.6 → 1.8
→ 6.7 → 1.4) and is best at the *fewest* slots. Full-period and out-of-sample
point in opposite directions, so the parameter is unresolved. Left at 2.

**Jev judging entry quality shows no predictive power.** Note these judgments
were produced **pre-repair**, on contaminated RS values and a leading prompt
("A stock broke out of a consolidation today…" asserts the conclusion before
asking whether the base is genuine). Treat as legacy evidence. 1,270 judgments across
two framings, 32 seconds, $0.052 total. Rank correlation with forward return:

| Feature | 20d | 60d |
|---|---|---|
| `jev_quality` (summary features) | +0.003 | +0.009 |
| `shape_quality` (serialised weekly bars) | −0.044 | **−0.077** |
| `shape_proper` | −0.056 | −0.052 |
| mechanical `rs_rating` | +0.038 | **+0.093** |

Jev's *worst*-rated bases returned +7.0% over 60 days; its *best*-rated
returned +1.5%. Three readings remain open and were not separated — see **D1**.

---

## 6. Why it holds 45% cash — measured, not assumed

| Cause | Share of days | Mean cash | Contribution |
|---|---|---|---|
| Regime RED — no buying allowed | 24.7% | 91.2% | **23 pts** |
| Regime YELLOW — book halved to 2 | 19.5% | 51.7% | **10 pts** |
| GREEN — genuine signal shortage | 55.8% | 18.2% | 10 pts |

**Three quarters of the cash is the market filter standing down on purpose**,
not an empty screen. On GREEN days the book holds 4.1 of 5 at 18% cash.
Average cash is 43%.

The RED block earns its keep — removing the filter entirely drops the weak half
to +3.2% and deepens drawdown to −27.6%. The YELLOW halving is the questionable
part and is **not O'Neil's rule**; it was invented by the first agent.

Signal shortage is real but secondary: 353 qualifying signals in 4.7 years,
on roughly one day in four.

---

## 7. Decisions you need to make

### D1 — Is the Jev entry null real, and does Jev belong in the loop at all?

Three explanations were never separated:

1. **Genuine null.** O'Neil's aesthetic criteria have never been independently
   validated; "tight orderly bases outperform" may simply be folklore, and
   obvious setups are also crowded ones. This would be a finding about O'Neil,
   not about Jev.
2. **Bad serialization.** Sixteen weekly OHLCV bars as text may not convey
   shape to a model optimised for classification.
3. **Wrong question.** The framing asked for a static aesthetic judgment. That
   was the agent's choice, not Jev's limit.

**Constraint:** six tests have already been run against the same 633 samples.
More framings tested on the same data is p-hacking. If you try another,
pre-register it and score it only on held-out folds.

**Alternative worth weighing:** point Jev at the **exit**. Be careful how this
is justified — an earlier version of this brief claimed the 50-day exits
"average roughly breakeven" and were "demonstrably costing money". **That was
false.** The 49 such exits average **+4.18%** (median +0.37%) and realise
+$36,591. The mean is carried by a few large winners while the median sits near
zero, which is interesting, but it is not evidence the rule loses money.

More importantly, return-since-entry cannot measure an exit rule at all. To
show the rule costs money you must compare selling against a *specified
continuation from the same trigger state* — same day, same position, hold
instead of sell, with a defined horizon and protection. That experiment has not
been run. Codex retracted its own recommendation to move Jev to exits on the
strength of the false claim, and so do I.

Other places Jev could sit, with what is known about each:

- **Ranking among same-day candidates** — only **12 days** in the whole run
  have more candidates than open slots. There is almost nothing here to win.
- **Position sizing by confidence** — do not. `Score`/`Choice` confidence
  summarises how peaked a probability distribution is. It is not the
  probability of a profitable trade and must not be used as a size multiplier.
  `Noul` returns a probability and has no separate confidence field at all.
- **Reading the market regime** — currently two moving-average comparisons,
  and the regime is responsible for three quarters of the cash drag.

### D2 — How to fix exposure, given every filter tried makes it worse

The pattern across every experiment: each knob moves exposure and none improves
selection. Options not yet tested:

- **Widen the universe** (~2,500 liquid US names instead of 586 large caps).
  Directly raises GREEN-day occupancy without touching the risk dial. O'Neil
  hunted every listed stock; mid-caps form proper bases far more often. Costs a
  long download and a slower signal build. Was offered once and declined.
- **O'Neil's secondary entries** — pullback to the 50-day line, three-weeks-
  tight. Adds buy points at the same quality bar rather than loosening it.
- **Accept it** and treat the strategy as a lower-exposure, lower-drawdown
  vehicle rather than an index-beater.

### D3 — What claim is the project actually trying to support?

These need different rigs and the current one only supports the first:

- *"Here is how an O'Neil rule set performed, honestly measured."* — done.
- *"Jev can trade stocks."* — requires Jev in the decision loop, which it is
  not, and requires the entry null to be resolved or routed around.
- *"An AI-designed strategy beats the market."* — not supported, and the
  walk-forward evidence argues against chasing it.

### D4 — Naming and publication honesty

The published artifact (<https://claude.ai/artifact/QXbxVVqwoKjPWnLgEZBMuh>)
and a draft social post both use "Jev" to mean the rule engine. Now that Jev is
known to be a real model that made none of those decisions, that is misleading.
Either relabel, or put Jev genuinely in the loop so the name is earned. This is
unresolved and blocks publication.

---

## 8. Traps

**Hindsight contamination via model recall.** Any model with a 2026 knowledge
cutoff *knows* what happened in this window. Show it `NVDA, 2024-01-09` and it
is recalling, not reasoning — which defeats the Wikipedia snapshots, the
next-open fills, and everything else. `src/jev.py` therefore anonymises every
`state`: no ticker, no date, no absolute price, scale-free features only. Keep
it that way. If you add a new question, anonymise it, and consider running a
contamination check (feed anonymised windows, ask the model to name the ticker
or year — if it can, the scheme has leaked).

**Structural choices were never walk-forwarded.** Walk-forward catches
parameter fitting. It cannot catch the fact that the first agent chose *which
rules exist at all* after seeing results — the trailing stop replaced the
profit target because NVDA was visibly cut short. That hand on the scale is
unmeasured and unmeasurable with the current rig. Treat the headline number as
optimistic.

**Split-half is robustness, not independence.** The whole 2022–2026 period has
already shaped structural choices, so walk-forward here remains exploratory. A
newly designated holdout does not undo that exposure. Real confirmation needs
genuinely unexamined data or a frozen prospective paper record. Also purge
overlapping outcome windows at fold boundaries and account for dependence
between nearby events and repeated issuer episodes.

**Repeated questions are not new observations.** Two prompt framings over the
same 635 events are not 1,270 independent market observations.

**Small sample.** 101 closed trades, one universe, 4.7 years, and a regime break
in the middle. A parameter worth 17 percentage points cannot be settled on
this much data.

**Tie-breaking.** `rs_rating` is rounded to whole numbers so ties are common.
A bug where `sort_values` broke ties by row order was fixed — rebuilding the
signal file silently changed which stocks were bought. Keep sorts deterministic.

**Agreed discipline.** Walk-forward, and accept a change only if it improves
**both halves** of the sample. Both were chosen deliberately; keep them.

---

## 9. Rebuild

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pandas numpy yfinance pyarrow requests lxml typesafe-sdk
.venv/bin/python src/universe.py        # ~40 Wikipedia revision snapshots (slow, rate-limited)
.venv/bin/python src/sectors.py         # GICS, same source
cd src
../.venv/bin/python data.py             # ~586 tickers of daily bars
../.venv/bin/python backtest.py         # signals.parquet + result.json
../.venv/bin/python jev_judge2.py       # Jev judgments (cached; free on re-run)
../.venv/bin/python walkforward.py      # out-of-sample record
../.venv/bin/python run_all.py          # web/data.js
```

Strategy parameters are all at the top of `src/strategy.py`. `TRAIL_PCT`,
`TRAIL_ATR` and `PROFIT_TARGET` are mutually exclusive; the 7% hard stop always
applies. Jev answers are cached by hash in `data/raw/jev_cache.json`, so
re-runs are free, offline and bit-identical — bump `QUESTION_VERSION` in
`src/jev.py` to invalidate deliberately.
