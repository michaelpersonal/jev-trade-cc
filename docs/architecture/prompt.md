# Redraw context — jev-trade-cc architecture

Trio: `index.html` (source of truth) · `architecture.png` (what README shows) ·
this file. Re-export the PNG from the HTML after any content change; never edit
the PNG. Read the evidence before drawing: this file, then `index.html`, then
the current PNG at full size, then `README.md` and `src/strategy.py` for
current terminology.

Export: `python3 -m http.server`, then headless Chrome at 1080×985.

## Must preserve

- **The central claim**: code owns risk and execution; Jev owns narrow judgment
  only. The two halves of the decision loop carry this and should stay
  side by side, code on the left.
- **All four Jev hooks drawn dashed at 55% opacity.** They are implemented and
  tested, and every one is shipped off. A reader must not come away thinking
  the model is trading.
- Each hook's outcome label on the right edge. Those are the findings, not
  decoration.
- The point-in-time caption on the data layer. It is the constraint the whole
  project exists to honour.
- `test_timing.py` pinned inside the code half — it guards the decision-time
  boundary and belongs where the boundary is.
- Top-to-bottom reading path: sources, point-in-time data, signals, decision
  loop, evaluation. Runtime architecture, per diagrams.md §4.

## Suggested additions

Facts in the repo the diagram does not yet show:

- The near-miss relaxation is now the shipped default (`NEARMISS_MODE = 3`)
  and is what takes the run past the index. It currently appears only as a
  disabled Jev hook, which understates the mechanical version's role.
- The walk-forward result (re-fitting loses to a fixed setting, 1 of 7 folds)
  would sharpen the evaluation layer if it fits without crowding.
- `data/pre_repair/` exists to keep pre-repair outputs uncitable. Worth a node
  only if the evaluation row gains space.

## Visual direction

- The evaluation row is the weakest band; its four nodes read as equals when
  `run_all.py` is really a terminal output step. Consider splitting it.
- The TypeSafe API node sits far right in the source row and its dashed edge
  runs the full height. If a redraw adds nodes, that edge will start crossing
  labels — move the API node down beside the Jev boundary instead.
- Do not add colour. One accent (ink blue) marks the model boundary; adding a
  second hue to distinguish hooks would break the maturity encoding, which is
  carried by stroke and opacity.

## Sister boundaries

- Strategy rules, parameters and their sweeps: `README.md` tables and
  `help-me-design.md`. Not this diagram.
- Why the portfolio sits in cash: `PARTICIPATION.md`. The gate attribution is
  its own subject and would overload this figure.
- Jev evaluation detail (corpus, rubric, calibration): `GUIDANCE_EVAL.md` and
  `NEARMISS_RESULT.md`.
