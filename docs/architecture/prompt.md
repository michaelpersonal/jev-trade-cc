# Redraw context — jev-trade-cc architecture

Trio: `index.html` (source of truth) · `architecture.png` (what README shows) ·
this file. Re-export the PNG from the HTML after any content change; never edit
the PNG. Read the evidence before drawing: this file, then `index.html`, then
the current PNG at full size, then `README.md` and `src/strategy.py` for
current terminology.

## Must preserve

- **The central claim**: code owns risk and execution; Jev owns narrow judgment
  and, on the exit, the whole hold-or-sell call. The two halves of the decision
  loop carry this and should stay side by side, code on the left.
- **Jev is ON.** `JEV_ENTRY`, `JEV_EXIT` and `JEV_EXIT_MODE = 2` all ship
  enabled. An earlier edition of this diagram drew every hook dashed because
  they were then shipped off, and said a reader "must not come away thinking the
  model is trading". That is now exactly backwards: the model IS trading, and
  the figure must say so.
- **The verdict block is not decoration and must not be dropped to save space.**
  The headline is $207,746 against the index's $159,500, and the paired
  jackknife says 7 of 12 — a coin. A diagram that shows the architecture without
  the measurement invites the reader to believe the headline.
- The point-in-time caption on the data layer, and the note that XBRL facts
  carry filing dates. That is the constraint the whole project exists to honour
  and the reason delisted names still have earnings.
- `anchor.py` beside the signals, feeding the loop: the base a position broke
  out of is frozen at the decision. Recomputing it from a rolling window
  inverted the sign of a real number in a real prompt.
- `test_timing.py` pinned inside the code half — it guards the decision-time
  boundary and belongs where the boundary is.
- Top-to-bottom reading path: sources, point-in-time data, signals, decision
  loop, evaluation, verdict. Runtime architecture, per diagrams.md §4.

## Export

`python3 -m http.server 8081 --directory docs/architecture`, then:

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=1080,1075 --screenshot=/tmp/arch.png \
  --virtual-time-budget=3000 http://127.0.0.1:8081/index.html
```

then trim the blank tail with Pillow (`ImageChops.difference` against the
background colour) and write `architecture.png`. Never edit the PNG.

## Suggested additions

Facts in the repo the diagram does not yet show:

- The 7.7% survivorship gap (49 of 635 members have no price data). It is the
  reason the jackknife deletes 49 and would justify a node on the data layer if
  one fits without crowding.
- `prove_fix.py` and its pre-registered baselines. The evaluation row is full;
  it would need the row split.
- The exit's abstention bound (`ABSTAIN_MAX`) and that confident holds are
  deliberately unbounded. Currently only the framing finding is shown.

## Visual direction

- The evaluation row and the verdict block now carry different weights on
  purpose: the row is machinery, the block is the finding. Keep the block
  full-width and stroked in the accent.
- Do not add colour. One accent (ink blue) marks the model boundary; adding a
  second hue to distinguish hooks would break the encoding, which is carried by
  stroke and fill.
- The EXIT block sits below the loop rather than inside it because the entry
  list already fills the Jev half. If the entry list ever shortens, consider
  bringing the exit back inside the loop frame where it logically belongs.

## Sister boundaries

- Strategy rules, parameters and their sweeps: `README.md` tables and
  `help-me-design.md`. Not this diagram.
- Why the portfolio sits in cash: `PARTICIPATION.md`. The gate attribution is
  its own subject and would overload this figure.
- Jev evaluation detail (corpus, rubric, calibration): `GUIDANCE_EVAL.md` and
  `NEARMISS_RESULT.md`.
