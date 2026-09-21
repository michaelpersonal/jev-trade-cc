"""One resolution of the switches into the policy that actually executes.

The flags used to be consulted individually at each call site, so the sites
disagreed with each other and with the record. `JEV_EXIT_MODE == 2` fired the
cadence review without ever consulting `JEV_EXIT`, and `JEV_EXIT_MODE == 0`
with `JEV_EXIT=True` still ran the legacy override; meanwhile the config in
the result omitted JEV_EXIT_MODE, JEV_SELECT and REVIEW_EVERY entirely, so
nothing in the output identified which policy had run.

Resolve once, obey the resolution everywhere, and write it down.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import strategy as S


@dataclass(frozen=True)
class Policy:
    jev_entry: bool
    jev_select: bool
    exit_path: str          # "none" | "override" | "review"
    nearmiss_mode: int
    review_every: int
    defer_max: int
    abstain_max: int
    error_rate_max: float
    review_abstain: str     # what an unclear cadence review does
    max_positions: int
    profit_target: float | None
    trail_pct: float | None
    trail_atr: float | None
    regime_mode: int
    yellow_slots: int | None
    macro_mode: int
    group_min_pct: float | None
    rs_min: int
    eps_growth_min: float | None
    notes: tuple[str, ...] = ()

    def as_record(self) -> dict:
        return asdict(self)


def resolve() -> Policy:
    notes = []

    # JEV_EXIT is the master switch; the mode only chooses WHICH exit hook.
    if not S.JEV_EXIT:
        path = "none"
        if S.JEV_EXIT_MODE:
            notes.append(f"JEV_EXIT off overrides JEV_EXIT_MODE="
                         f"{S.JEV_EXIT_MODE}; no exit hook runs")
    elif S.JEV_EXIT_MODE == 1:
        path = "override"
    elif S.JEV_EXIT_MODE == 2:
        path = "review"
    else:
        path = "none"
        notes.append("JEV_EXIT on but JEV_EXIT_MODE=0; no exit hook runs")

    # Selection and the mechanical near-miss path share the same slots, so a
    # refusal must not be filled by the other. Resolved here, once.
    nm = S.NEARMISS_MODE
    if S.JEV_SELECT and nm:
        notes.append(f"JEV_SELECT on disables NEARMISS_MODE={nm}")
        nm = 0

    return Policy(
        jev_entry=bool(S.JEV_ENTRY), jev_select=bool(S.JEV_SELECT),
        exit_path=path, nearmiss_mode=nm, review_every=S.REVIEW_EVERY,
        defer_max=S.DEFER_MAX, abstain_max=S.ABSTAIN_MAX,
        error_rate_max=S.ERROR_RATE_MAX, review_abstain=REVIEW_ABSTAIN,
        max_positions=S.MAX_POSITIONS, profit_target=S.PROFIT_TARGET,
        trail_pct=S.TRAIL_PCT, trail_atr=S.TRAIL_ATR,
        regime_mode=S.REGIME_MODE, yellow_slots=S.YELLOW_SLOTS,
        macro_mode=S.MACRO_MODE, group_min_pct=S.GROUP_MIN_PCT,
        rs_min=S.RS_MIN, eps_growth_min=S.EPS_GROWTH_MIN,
        notes=tuple(notes))


# An unclear cadence review is an abstention, not a decision to hold. Under
# the override contract an abstention lets the pending rule act. There is no
# pending rule on a routine review, so "keep" is the only coherent default --
# but it is a DECLARED default, recorded as an abstention rather than being
# reported as a confident hold, and it does not extend any deferral clock.
REVIEW_ABSTAIN = "keep"
