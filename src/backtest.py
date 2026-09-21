"""Day-by-day simulation of the O'Neil rules. $100k, long-only, no margin.

Timing contract -- the thing that makes or breaks an honest backtest:

  * Signals on day t are computed from bars up to and including day t's close.
  * Discretionary orders (buys, trend-break sells) fill at day t+1's OPEN.
  * The 7% stop and the 25% target are standing orders placed in advance, so
    they fill intraday on day t against that day's high/low -- this is not
    lookahead, it is what a resting stop-market order actually does.
  * The tradeable universe on day t is the most recent Wikipedia snapshot
    dated on or before t.

Nothing in the loop may read a row with a date greater than t.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import anchor as A
import fundamentals as FU
import jev as J
import macro as MAC
import policy as P
import strategy as S
import universe as U

ROOT = Path(__file__).resolve().parent.parent
START, END = "2022-01-03", "2026-09-18"
CAPITAL = 100_000.0
SLIPPAGE = 0.0005      # 5bp each side
COMMISSION = 0.0       # modern retail


def _why_buy(rows, tkr) -> str:
    rs = rows.at[tkr, "rs_rating"]
    return f"breakout RS{int(rs)}" if np.isfinite(rs) else "breakout"


class Position:
    __slots__ = ("ticker", "shares", "entry", "entry_date", "entry_idx",
                 "stop", "target", "hold_until", "peak", "peak_high",
                 "below_ma_days", "defer_start", "anchor", "abstains")

    def __init__(self, ticker, shares, entry, entry_date, entry_idx,
                 anchor=None):
        # The base this position broke out of, frozen at the decision and
        # never recomputed. See anchor.py.
        self.anchor = anchor
        self.abstains = 0   # consecutive 'unclear' reviews
        self.ticker, self.shares = ticker, shares
        self.entry, self.entry_date, self.entry_idx = entry, entry_date, entry_idx
        self.stop = entry * (1 - S.STOP_LOSS)
        # PROFIT_TARGET None = let winners run; exit only on the stop or a
        # break of the 50-day line.
        self.target = (entry * (1 + S.PROFIT_TARGET)
                       if S.PROFIT_TARGET else float("inf"))
        self.hold_until = None       # set if the 8-week rule kicks in
        self.peak = entry          # highest close since entry
        self.peak_high = entry     # highest intraday high since entry
        self.below_ma_days = 0
        self.defer_start = None    # index the current deferral episode opened


_PANEL: dict = {}
_WEEKLY: dict = {}
_ASSESS: dict = {}          # (date, ticker) -> Jev's assessment of that setup
_ASSESS_FP: str | None = None   # provenance of the artifact they came from
_FUND: pd.DataFrame | None = None   # point-in-time SEC earnings facts


def load_assessments(df, manifest: dict | None = None,
                     require_current: bool = True) -> None:
    """Phase-A assessments, keyed for the day loop.

    An assessment artifact is only meaningful alongside the criteria that
    produced it. Without this check a parquet written by an older edition of
    ASSESS loaded silently and the run reported Jev's current judgment while
    replaying its previous one. `require_current=False` is for deliberately
    inspecting an old artifact, never for producing a result.
    """
    global _ASSESS, _ASSESS_FP
    want = J.question_fingerprint(J.ASSESS, "assess")
    got = (manifest or {}).get("question_fingerprint")
    if require_current:
        if got is None:
            raise RuntimeError(
                "assessment artifact has no manifest: cannot tell which "
                "criteria judged these rows. Re-run jev_select.py.")
        if got != want:
            raise RuntimeError(
                f"assessment artifact was written by different criteria "
                f"({got}), current ASSESS is {want}. Re-run jev_select.py.")
        if manifest.get("partial"):
            raise RuntimeError(
                f"assessment artifact is a PARTIAL run "
                f"({manifest.get('returned')} of {manifest.get('requested')} "
                f"rows); it is not a universe.")
    _ASSESS_FP = got
    # An error or a missing history is not an assessed negative. Only rows the
    # model actually answered become assessments; the rest stay absent, so a
    # zero-candidate day can be told apart from a day nothing was asked about.
    if "status" in df.columns:
        df = df[df["status"] == "ok"]
    _ASSESS = {(pd.Timestamp(r.date), r.ticker): dict(
        setup=r.setup, supply=r.supply, prior_advance=r.prior_advance,
        pattern=getattr(r, "pattern", None),
        earnings=getattr(r, "earnings", None),
        pattern_conf=getattr(r, "pattern_conf", None))
        for r in df.itertuples(index=False)}


def load_fundamentals(df: pd.DataFrame | None) -> None:
    """Point-in-time SEC earnings. Absent is allowed; silently wrong is not."""
    global _FUND
    _FUND = df


def earnings_state(ticker: str, upto) -> str | None:
    """The earnings a trader could have read on `upto`, as prose, or None."""
    if _FUND is None:
        return None
    return FU.describe(FU.pit(_FUND, ticker, upto))


def load_panel(panel: pd.DataFrame) -> None:
    """Give weekly_bars its price history. Call once before a Jev run.

    Clears the derived weekly cache: entries built from a previous panel --
    including cached `None` misses from before initialisation -- must not
    survive a reload.
    """
    global _PANEL
    _WEEKLY.clear()
    p = panel.sort_values(["ticker", "date"]).copy()
    p["vol_rel"] = p["volume"] / p.groupby("ticker")["volume"].transform(
        lambda v: v.rolling(50).mean())
    _PANEL = {t: g.set_index("date") for t, g in p.groupby("ticker")}


def since_entry(ticker: str, entry_date, upto, entry: float) -> dict | None:
    """Compact summary of the whole holding, so the bar window can stay short.

    Plan 2.4: the window was ten fixed days, which cannot show whether a
    60-session advance is ending. Emitting every daily bar instead would put
    200 lines in the prompt of a long holding. This carries the shape of the
    full holding in a few numbers, alongside the last 20 bars in detail.
    """
    g = _PANEL.get(ticker)
    if g is None or entry <= 0:
        return None
    g = g[(g.index >= pd.Timestamp(entry_date)) & (g.index <= upto)]
    if len(g) < 3:
        return None
    c = g["close"].to_numpy()
    v = g["vol_rel"].fillna(1.0).to_numpy()
    up = c[1:] > c[:-1]
    dn = c[1:] < c[:-1]
    peak = np.maximum.accumulate(c)
    return dict(
        sessions=len(g),
        peak_gain=(peak[-1] / entry - 1) * 100,
        max_giveback=float(np.max((peak - c) / peak) * 100),
        up_vol=float(v[1:][up].mean()) if up.any() else float("nan"),
        dn_vol=float(v[1:][dn].mean()) if dn.any() else float("nan"),
        heavy_down=int(((v[1:] > 1.25) & dn).sum()),
        heavy_up=int(((v[1:] > 1.25) & up).sum()))


def rs_direction(by_date, dates, i, ticker, lookback: int = 40) -> float | None:
    """Change in relative-strength RANK over `lookback` sessions.

    Plan 2.2: the prompt carried today's rank only. O'Neil sells on
    DETERIORATING relative strength -- the direction is the signal, the level
    is not. rs_rating lives in the signals table rather than the price panel,
    so this reads the same by_date the loop already holds; a helper hung off
    _PANEL would have returned None forever and nothing would have said so.
    """
    j = i - lookback
    if j < 0:
        return None
    then = by_date.get(dates[j])
    now = by_date.get(dates[i])
    if then is None or now is None:
        return None
    if ticker not in then.index or ticker not in now.index:
        return None
    a, b = then.at[ticker, "rs_rating"], now.at[ticker, "rs_rating"]
    if not (np.isfinite(a) and np.isfinite(b)):
        return None
    return float(b - a)


def recent_bars(ticker: str, upto, entry: float, days: int = 20):
    """Trailing daily bars rebased so the entry price is 100.

    The exit question asks about closes near the lows and undercuts that
    recover. Without this the state carried neither, and Jev abstained on 95%
    of exits because it genuinely could not tell.
    """
    g = _PANEL.get(ticker)
    if g is None or entry <= 0:
        return None
    g = g[g.index <= upto].tail(days)
    if len(g) < 3:
        return None
    return pd.DataFrame(dict(
        ago=range(len(g) - 1, -1, -1),
        rel=g["close"].to_numpy() / entry * 100,
        lo_rel=g["low"].to_numpy() / entry * 100,
        hi_rel=g["high"].to_numpy() / entry * 100,
        high=g["high"].to_numpy(), low=g["low"].to_numpy(),
        close=g["close"].to_numpy(),
        vol_rel=g["vol_rel"].fillna(1.0).to_numpy()))


def weekly_bars(ticker: str, upto, weeks: int = 16):
    """Trailing weekly bars ending on `upto` -- the same evidence the entry
    evaluation used. Nothing after `upto` is visible."""
    key = (ticker, upto, weeks)   # lookback is part of the identity
    if key in _WEEKLY:
        return _WEEKLY[key]
    g = _PANEL.get(ticker)
    if g is None:
        _WEEKLY[key] = None
        return None
    g = g[g.index <= upto].tail(260)
    w = g.resample("W").agg(open=("open", "first"), high=("high", "max"),
                            low=("low", "min"), close=("close", "last"),
                            vol_rel=("vol_rel", "mean")).dropna().tail(weeks)
    _WEEKLY[key] = w
    return w


def _log(ledger, date, ticker, kind, status, baseline, action,
         value=None, detail=None) -> None:
    """One immutable row per decision Jev was asked for, so a result can be
    traced back to what the model was asked and what the rule would have done."""
    ledger.append(dict(date=str(pd.Timestamp(date).date()), ticker=ticker,
                       kind=kind, status=status, baseline=baseline,
                       action=action, value=value, detail=detail))


def index_by_date(sig: pd.DataFrame) -> dict:
    """date -> rows indexed by ticker. Built once and reused across runs."""
    return {d: g.set_index("ticker") for d, g in sig.groupby("date")}


def run(sig: pd.DataFrame, idx: pd.DataFrame, memb: dict, *,
        start: str | None = None, end: str | None = None,
        capital: float | None = None, by_date: dict | None = None,
        feat: pd.DataFrame | None = None) -> dict:
    pol = P.resolve()          # the executed policy, resolved once
    for n in pol.notes:
        print(f"  policy: {n}")
    regime = S.market_regime(idx)
    if S.MACRO_MODE and feat is not None:
        regime = MAC.apply_regime(regime, feat, S.MACRO_MODE, S.MAX_POSITIONS)
    start, end = start or START, end or END
    capital = CAPITAL if capital is None else capital
    dates = [d for d in sorted(sig["date"].unique())
             if pd.Timestamp(start) <= d <= pd.Timestamp(end)]

    # date -> {ticker -> row dict}, so the loop never touches a future row
    if by_date is None:
        by_date = index_by_date(sig)

    cash = capital
    jev_holds = [0]                     # times Jev overrode a mechanical sell
    errors = [0]                        # inference failures, never a decision
    nm_taken: dict = {}                 # date -> near-misses admitted
    ledger: list[dict] = []             # every decision Jev was asked for
    prev_max_pos: int | None = None     # last night's position limit
    positions: dict[str, Position] = {}
    pending_buys: list[A.Anchor] = []
    pending_sells: list[tuple[str, str]] = []
    equity_curve, trades, daily = [], [], []

    for i, today in enumerate(dates):
        rows = by_date.get(today)
        if rows is None:
            continue
        reg = regime.loc[today] if today in regime.index else None
        regime_name = reg["regime"] if reg is not None else "YELLOW"
        # `max_pos` is read from TODAY's close and therefore may only inform
        # orders queued for tomorrow. Orders filling at today's open were
        # placed last night and are governed by last night's limit -- reading
        # today's close here would let information from after the fill decide
        # whether the fill happens.
        max_pos = int(reg["max_positions"]) if reg is not None else S.MAX_POSITIONS
        max_pos_at_open = prev_max_pos if prev_max_pos is not None else max_pos
        todays_trades = []

        def px(t, field):
            return float(rows.at[t, field]) if t in rows.index else np.nan

        # --- 1. fill yesterday's discretionary SELLS at today's open --------
        for tkr, why in pending_sells:
            p = positions.get(tkr)
            if p is None or tkr not in rows.index:
                continue
            fill = px(tkr, "open") * (1 - SLIPPAGE)
            proceeds = p.shares * fill - COMMISSION
            cash += proceeds
            pnl = (fill - p.entry) * p.shares
            trades.append(dict(date=str(today.date()), ticker=tkr, side="SELL",
                               shares=p.shares, price=round(fill, 2),
                               reason=why, pnl=round(pnl, 2),
                               pct=round((fill / p.entry - 1) * 100, 2),
                               held=i - p.entry_idx))
            todays_trades.append(trades[-1])
            del positions[tkr]
        pending_sells = []

        # --- 2. fill yesterday's BUYS at today's open ----------------------
        equity_now = cash + sum(p.shares * px(t, "open") for t, p in positions.items()
                                if t in rows.index)
        for anc in pending_buys:
            tkr = anc.ticker
            if (tkr in positions or len(positions) >= max_pos_at_open
                    or tkr not in rows.index):
                continue
            o = px(tkr, "open")
            if not np.isfinite(o) or o <= 0:
                continue
            fill = o * (1 + SLIPPAGE)
            budget = min(equity_now / S.MAX_POSITIONS, cash)
            shares = int(budget // fill)
            if shares <= 0:
                continue
            cost = shares * fill + COMMISSION
            cash -= cost
            positions[tkr] = Position(tkr, shares, fill, today, i, anc)
            trades.append(dict(date=str(today.date()), ticker=tkr, side="BUY",
                               shares=shares, price=round(fill, 2),
                               reason=_why_buy(rows, tkr),
                               pnl=0.0, pct=0.0, held=0))
            todays_trades.append(trades[-1])
        pending_buys = []

        # --- 3. standing stop / target orders, intraday ---------------------
        # The stop level for day t is built from peaks through day t-1's close,
        # because step 4 updates the peaks only after this block has run.
        for tkr in list(positions):
            p = positions[tkr]
            if tkr not in rows.index:
                continue
            lo, hi, op = px(tkr, "low"), px(tkr, "high"), px(tkr, "open")
            level, why = p.stop, "stop -7%"        # the hard stop never loosens
            if S.TRAIL_PCT:
                t = p.peak * (1 - S.TRAIL_PCT)
                if t > level:
                    level, why = t, f"trail -{S.TRAIL_PCT:.0%}"
            elif S.TRAIL_ATR:
                atr = px(tkr, "atr20_prev")   # today's ATR includes today's range
                if np.isfinite(atr):
                    t = p.peak_high - S.TRAIL_ATR * atr
                    if t > level:
                        level, why = t, f"chandelier {S.TRAIL_ATR:g}x ATR"
            exit_px = None
            if lo <= level:                        # gap-through fills at the open
                exit_px = min(level, op)
            elif p.hold_until is None and hi >= p.target:
                exit_px, why = max(p.target, op), "target +25%"
            if exit_px is not None:
                fill = exit_px * (1 - SLIPPAGE)
                cash += p.shares * fill - COMMISSION
                trades.append(dict(date=str(today.date()), ticker=tkr, side="SELL",
                                   shares=p.shares, price=round(fill, 2),
                                   reason=why, pnl=round((fill - p.entry) * p.shares, 2),
                                   pct=round((fill / p.entry - 1) * 100, 2),
                                   held=i - p.entry_idx))
                todays_trades.append(trades[-1])
                del positions[tkr]

        # --- 4. mark to market on today's close ----------------------------
        held_value = 0.0
        for tkr, p in positions.items():
            c, h = px(tkr, "close"), px(tkr, "high")
            if np.isfinite(c):
                p.peak = max(p.peak, c)
                if np.isfinite(h):
                    p.peak_high = max(p.peak_high, h)
                held_value += p.shares * c
        equity = cash + held_value
        equity_curve.append(equity)

        # --- 5. signals from today's close -> orders for tomorrow ----------
        for tkr, p in positions.items():
            if tkr not in rows.index:
                continue
            c, ma50 = px(tkr, "close"), px(tkr, "ma50")
            held = i - p.entry_idx

            # O'Neil's 8-week rule: a 20% gain inside three weeks marks a
            # potential big winner -- stop taking the 25% and let it run.
            if p.hold_until is None and held <= S.FAST_MOVE_DAYS \
                    and c >= p.entry * (1 + S.FAST_MOVE):
                p.hold_until = i + S.HOLD_WEEKS * 5
            if p.hold_until is not None and i >= p.hold_until:
                p.hold_until = None
                p.target = c * 1.10 if S.PROFIT_TARGET else float("inf")

            p.below_ma_days = p.below_ma_days + 1 if (
                np.isfinite(ma50) and c < ma50) else 0
            need = 1 if regime_name == "RED" else 2

            # --- mode 2: Jev reviews the holding on its own schedule -------
            # No rule has to trigger. Jev can sell a position the 50-day rule
            # is content with, which the override framing could never do.
            if pol.exit_path == "review" and tkr in rows.index:
                due = (held > 0 and held % pol.review_every == 0)
                if due or p.below_ma_days >= need:
                    row = rows.loc[tkr].to_dict()
                    row["regime"] = regime_name
                    # The base THIS position broke out of. Today's rolling
                    # high climbs with the stock and inverted this number's
                    # sign; see anchor.py.
                    piv = p.anchor.base_top if p.anchor else float("nan")
                    stop_gap = (1 - max(p.stop, p.peak * (1 - S.TRAIL_PCT)
                                        if S.TRAIL_PCT else p.stop) / c) * 100
                    try:
                        d = J.review_holding(
                            row, gain_pct=(c / p.entry - 1) * 100,
                            days_held=held,
                            peak_gain_pct=(p.peak / p.entry - 1) * 100,
                            below_ma_days=p.below_ma_days,
                            stop_distance_pct=max(0.0, stop_gap),
                            recent=recent_bars(tkr, today, p.entry),
                            pivot_distance_pct=(
                                (c / piv - 1) * 100
                                if np.isfinite(piv) and piv > 0 else None),
                            eight_week_left=(p.hold_until - i
                                             if p.hold_until is not None else None),
                            earnings=earnings_state(tkr, today),
                            rs_change=rs_direction(by_date, dates, i, tkr),
                            holding=since_entry(tkr, p.entry_date, today,
                                                p.entry))
                        act = J.choice_of(d, "action",
                                          {"hold", "sell", "unclear"})
                    except Exception as exc:
                        # An inference failure is not a decision to hold. It
                        # hands the decision back to the mechanical rule and
                        # is recorded against the RUN, never credited to Jev.
                        # In this mode there is no other backstop, so treating
                        # an outage as "hold" would silently keep every
                        # position open and still print a final number.
                        errors[0] += 1
                        mech = "sell" if p.below_ma_days >= need else "hold"
                        _log(ledger, today, tkr, "review", "error",
                             baseline=mech, action=mech, detail=str(exc)[:120])
                        act = "_fallback_" + mech
                    else:
                        _log(ledger, today, tkr, "review",
                             "abstain" if act == "unclear" else "ok",
                             baseline="hold" if p.below_ma_days < need else "sell",
                             action=act, value=held)

                    if act == "unclear":
                        # Declared policy, enforced here rather than falling
                        # through an if/elif and landing on the right answer
                        # by accident. Repeated abstention is bounded; a
                        # confident hold is not.
                        p.abstains += 1
                        if p.abstains > pol.abstain_max:
                            act = ("sell" if p.below_ma_days >= need
                                   else "hold")
                            _log(ledger, today, tkr, "review", "abstain_expired",
                                 baseline=act, action=act, value=p.abstains)
                            # The episode is over: the mechanical rule has
                            # taken this decision. Reset, so the next run of
                            # abstentions is counted from zero rather than
                            # re-expiring on every subsequent review.
                            p.abstains = 0
                        else:
                            act = pol.review_abstain      # "keep"
                    elif not act.startswith("_fallback_"):
                        p.abstains = 0

                    if act in ("sell", "_fallback_sell"):
                        pending_sells.append(
                            (tkr, "Jev: advance over" if act == "sell"
                             else "50dma rule (inference failed)"))
                    elif act == "hold" and p.below_ma_days >= need:
                        jev_holds[0] += 1
                continue

            if p.below_ma_days >= need:
                if pol.exit_path == "override":
                    # Bounded deferral, per src/deferral_contract.md. Jev may
                    # keep a position for at most DEFER_MAX sessions from the
                    # day the mechanical exit first qualified; after that it is
                    # sold regardless. Protective stops are unaffected.
                    if p.defer_start is None:
                        p.defer_start = i
                    left = pol.defer_max - (i - p.defer_start)
                    if left <= 0:
                        pending_sells.append((tkr, "Jev: deferral expired"))
                        _log(ledger, today, tkr, "exit", "expired",
                             baseline="sell", action="sell")
                    else:
                        row = rows.loc[tkr].to_dict()
                        row["regime"] = regime_name
                        stop_gap = (1 - max(p.stop, p.peak * (1 - S.TRAIL_PCT)
                                            if S.TRAIL_PCT else p.stop) / c) * 100
                        try:
                            piv = (p.anchor.base_top if p.anchor
                                   else float("nan"))
                            d = J.decide_exit(
                                row, gain_pct=(c / p.entry - 1) * 100,
                                days_held=held,
                                peak_gain_pct=(p.peak / p.entry - 1) * 100,
                                below_ma_days=p.below_ma_days,
                                sessions_left=left,
                                stop_distance_pct=max(0.0, stop_gap),
                                recent=recent_bars(tkr, today, p.entry),
                                pivot_distance_pct=(
                                    (c / piv - 1) * 100
                                    if np.isfinite(piv) and piv > 0 else None),
                                eight_week_left=(
                                    p.hold_until - i
                                    if p.hold_until is not None else None),
                                earnings=earnings_state(tkr, today),
                                rs_change=rs_direction(by_date, dates, i, tkr),
                                holding=since_entry(tkr, p.entry_date, today,
                                                    p.entry))
                            act = J.choice_of(
                                d, "action",
                                {"override", "let_it_sell", "unclear"})
                        except Exception as exc:
                            # Failure falls back to the mechanical rule and is
                            # recorded as a failure, never credited to Jev.
                            errors[0] += 1
                            _log(ledger, today, tkr, "exit", "error",
                                 baseline="sell", action="sell",
                                 detail=str(exc)[:120])
                            pending_sells.append(
                                (tkr, f"broke 50dma ({regime_name}) [fallback]"))
                            act = None
                        if act == "let_it_sell":
                            pending_sells.append((tkr, "broke 50dma (Jev agreed)"))
                            _log(ledger, today, tkr, "exit", "ok",
                                 baseline="sell", action="sell")
                        elif act == "unclear":
                            # An abstention is not a decision to hold. Defer to
                            # the mechanical rule and record it as an
                            # abstention, distinct from an inference failure.
                            pending_sells.append((tkr, "broke 50dma (abstain)"))
                            _log(ledger, today, tkr, "exit", "abstain",
                                 baseline="sell", action="sell")
                        elif act == "override":
                            jev_holds[0] += 1
                            _log(ledger, today, tkr, "exit", "ok",
                                 baseline="sell", action="hold", value=left)
                else:
                    pending_sells.append((tkr, f"broke 50dma ({regime_name})"))
            elif pol.exit_path == "override" and p.defer_start is not None:
                p.defer_start = None      # recovered above the 50-day: reset

        sell_set = {t for t, _ in pending_sells}
        open_slots = max_pos - (len(positions) - len(sell_set))
        # Candidates that exist TODAY irrespective of regime, capacity or
        # ranking. Needed to tell "no stock qualified" apart from "a rule
        # stopped us buying one that did".
        live_today = memb_on(today, memb)
        avail = rows[rows["buyable"].fillna(False)]
        n_available = int(avail.index.isin(live_today).sum()
                          - avail.index.isin(positions).sum())
        n_cands = n_cands_pre = 0
        if open_slots > 0 and regime_name != "RED":
            live = set(memb_on(today, memb))
            if pol.jev_select:
                # Candidates are every eligible name Jev judged a valid setup.
                # No quality threshold of mine stands between them and the
                # decision; code enforces only membership and holdings.
                pool = [t for t in rows.index
                        if t in live and t not in positions
                        and _ASSESS.get((today, t), {}).get("setup") == "valid"]
                cands = rows.loc[pool]
            else:
                cands = rows[rows["buyable"].fillna(False)]
            cands = cands[cands.index.isin(live) & ~cands.index.isin(positions)]
            if S.EPS_GROWTH_MIN is not None and _FUND is not None and len(cands):
                keep = [t for t in cands.index
                        if (FU.pit(_FUND, t, today).get("eps_q_growth") or
                            float("-inf")) >= S.EPS_GROWTH_MIN]
                cands = cands.loc[keep]
            if S.GROUP_MIN_PCT and "group_pct" in cands.columns:
                # Buy leaders of leading groups. An unclassified name passes
                # rather than being dropped: the gaps are Nasdaq-only listings,
                # heavily semis, so excluding them would bias against exactly
                # the groups this filter exists to find.
                gp = cands["group_pct"]
                cands = cands[gp.isna() | (gp >= S.GROUP_MIN_PCT)]
            n_cands_pre = len(cands)      # opportunities before any model filter
            if pol.jev_entry and len(cands):
                if not _PANEL:
                    raise RuntimeError(
                        "JEV_ENTRY is on but no price history is loaded. Call "
                        "backtest.load_panel(panel) first. Refusing to run: "
                        "without it every candidate is skipped and the result "
                        "silently looks like a legitimate all-cash strategy.")
                keep, conv = [], {}
                for tkr in cands.index:
                    row = cands.loc[tkr].to_dict()
                    row["regime"] = regime_name
                    bars = weekly_bars(tkr, today)
                    if bars is None or len(bars) < 8:
                        _log(ledger, today, tkr, "entry", "no_evidence",
                             baseline="buy", action="skip")
                        continue
                    try:
                        d = J.decide_entry(row, bars,
                                           earnings_state(tkr, today))
                        act, strength = J.entry_policy(d)
                    except Exception as exc:
                        # An inference failure is not a decision to skip. It is
                        # recorded as a failure and the run is marked degraded.
                        errors[0] += 1
                        _log(ledger, today, tkr, "entry", "error",
                             baseline="buy", action="skip", detail=str(exc)[:120])
                        continue
                    _log(ledger, today, tkr, "entry", "ok", baseline="buy",
                         action=act, value=strength)
                    if act == "buy":
                        keep.append(tkr)
                        conv[tkr] = strength
                cands = cands.loc[keep]
                if len(cands):
                    cands = cands.assign(
                        jev_conviction=[conv[t] for t in cands.index])
            n_cands = len(cands)
            # Rank by Jev's conviction when Jev is choosing, else by RS.
            # rs_rating is rounded to whole numbers so ties are common; break
            # them on ticker, otherwise the result depends on row order.
            rank_key = ("jev_conviction"
                        if pol.jev_entry and "jev_conviction" in cands.columns
                        else "rs_rating")
            if pol.jev_select and len(cands):
                # Jev sees the competitors in one question and picks one, or
                # none. This is the step the reranking design never had.
                opts, key = {}, {}
                # Order alphabetically, NOT by relative strength. Ranking the
                # options by RS before showing them would let RS decide which
                # candidates Jev sees and in what order, which is the selection
                # this design is supposed to hand over. A cap still applies as
                # a prompt-size limit, and when it binds it is recorded.
                ranked = cands.sort_index(kind="mergesort")
                truncated = max(0, len(ranked) - 10)
                ranked = ranked.head(10)
                for n, tkr in enumerate(ranked.index):
                    rr = ranked.loc[tkr]
                    lbl = chr(65 + n)          # A, B, C ... never the ticker
                    key[lbl] = tkr
                    aa = _ASSESS.get((today, tkr), {})
                    anc = A.from_row(rr, tkr, today, "jev_select", aa,
                                     _ASSESS_FP)
                    opts[lbl] = (
                        f"{anc.pattern_phrase()}, "
                        f"{anc.base_len_wk:.0f} weeks long and "
                        f"{anc.base_depth*100:.0f}% deep; close is "
                        f"{anc.distance_pct(rr['close']):+.1f}% from its buy "
                        f"point; volume today {rr['vol_ratio']:.1f}x average; "
                        f"supply dried up and expanded {aa.get('supply', 0):.2f}; "
                        f"prior advance {aa.get('prior_advance', 0):.2f}; "
                        f"earnings growth O'Neil would want "
                        f"{aa.get('earnings', 0):.2f}; "
                        f"relative strength {int(rr['rs_rating'])} of 99")
                state = "\n".join(f"Option {k}: {v}" for k, v in opts.items())
                try:
                    ans = J.ask(state, J.select_question(opts), "select_v1")
                    pick = J.choice_of(ans, "pick", set(opts) | {"none"})
                except Exception as exc:
                    errors[0] += 1
                    _log(ledger, today, "-", "select", "error",
                         baseline=cands["rs_rating"].idxmax(), action="none",
                         detail=str(exc)[:120])
                    pick = "none"
                else:
                    _log(ledger, today, key.get(pick, "-"), "select", "ok",
                         baseline=cands["rs_rating"].idxmax(), action=pick,
                         value=len(opts),
                         detail=f"truncated={truncated}" if truncated else None)
                pending_buys = ([A.from_row(
                    rows.loc[key[pick]], key[pick], today, "jev_select",
                    _ASSESS.get((today, key[pick])), _ASSESS_FP)]
                    if pick in key else [])
                jev_declined = pick not in key
            else:
                jev_declined = False
                picked = (cands.sort_values(rank_key, ascending=False,
                                            kind="mergesort")
                          .sort_index(kind="mergesort")
                          .sort_values(rank_key, ascending=False,
                                       kind="mergesort")
                          .index[:open_slots].tolist())
                pending_buys = [A.from_row(rows.loc[t], t, today, "screen")
                                for t in picked]

            # --- near-miss adjudication (prereg_nearmiss.md) ---------------
            # Strict candidates take slots first; near-misses fill what is
            # left. This is the only path by which a model can INCREASE the
            # supply of candidates rather than filter one the rules built.
            spare = open_slots - len(pending_buys)
            # Selection/near-miss interlock is resolved in policy.py.
            if pol.jev_select and jev_declined:
                _log(ledger, today, "-", "select", "declined",
                     baseline="-", action="none", detail="no buy this session")
            if pol.nearmiss_mode and spare > 0:
                nm = rows[rows["nearmiss"].fillna(False)]
                # The gate must apply to every path into the book. Gating only
                # the strict pool made the portfolio buy MORE (123 vs 116),
                # because each rejected breakout freed a slot for an ungated
                # near-miss -- the filter quietly became a swap.
                if S.EPS_GROWTH_MIN is not None and _FUND is not None and len(nm):
                    nm = nm.loc[[t for t in nm.index
                                 if (FU.pit(_FUND, t, today).get("eps_q_growth")
                                     or float("-inf")) >= S.EPS_GROWTH_MIN]]
                nm = nm[nm.index.isin(live) & ~nm.index.isin(positions)
                        & ~nm.index.isin([a.ticker for a in pending_buys])]
                taken: list[str] = []
                if len(nm):
                    if pol.nearmiss_mode == 1:            # Jev adjudicates
                        if not _PANEL:
                            raise RuntimeError(
                                "NEARMISS_MODE=1 needs price history; call "
                                "backtest.load_panel(panel) first.")
                        keep, sc = [], {}
                        for tkr in nm.index:
                            row = nm.loc[tkr].to_dict()
                            row["regime"] = regime_name
                            bars = weekly_bars(tkr, today)
                            if bars is None or len(bars) < 8:
                                continue
                            try:
                                d = J.decide_entry(row, bars,
                                               earnings_state(tkr, today))
                                act, sc[tkr] = J.entry_policy(d)
                            except Exception as exc:
                                errors[0] += 1
                                _log(ledger, today, tkr, "nearmiss", "error",
                                     baseline="skip", action="skip",
                                     detail=str(exc)[:120])
                                continue
                            _log(ledger, today, tkr, "nearmiss", "ok",
                                 baseline="skip", action=act, value=sc[tkr])
                            if act == "buy":
                                keep.append(tkr)
                        taken = sorted(keep, key=lambda t: (-sc[t], t))[:spare]
                    else:                                # mechanical control
                        quota = (S.NEARMISS_QUOTA.get(str(pd.Timestamp(today).date()), 0)
                                 if pol.nearmiss_mode == 2 else spare)
                        n = min(spare, quota)
                        taken = (nm.sort_values("rs_rating", ascending=False,
                                                kind="mergesort")
                                 .sort_index(kind="mergesort")
                                 .sort_values("rs_rating", ascending=False,
                                              kind="mergesort")
                                 .index[:n].tolist())
                pending_buys += [A.from_row(rows.loc[t], t, today, "nearmiss")
                                 for t in taken]
                nm_taken[str(pd.Timestamp(today).date())] = len(taken)

        prev_max_pos = max_pos     # tonight's limit governs tomorrow's opens
        daily.append(dict(
            date=str(today.date()), equity=round(equity, 2), cash=round(cash, 2),
            regime=regime_name, slots=max_pos, open_slots=max(0, open_slots),
            n_cands=n_cands, n_cands_pre_jev=n_cands_pre,
            n_available=max(0, n_available), n_held=len(positions),
            positions=[dict(t=t, sh=p.shares, entry=round(p.entry, 2),
                            px=round(px(t, "close"), 2),
                            pct=round((px(t, "close") / p.entry - 1) * 100, 1),
                            val=round(p.shares * px(t, "close"), 0))
                       for t, p in sorted(positions.items())
                       if np.isfinite(px(t, "close"))],
            trades=todays_trades))

    asked = len([x for x in ledger if x.get("kind") in
                 ("entry", "exit", "review", "select", "nearmiss")])
    err_rate = (errors[0] / asked) if asked else 0.0
    incomplete = err_rate > pol.error_rate_max
    if incomplete:
        print(f"  *** INCOMPLETE: {errors[0]} of {asked} required inferences "
              f"failed ({err_rate:.1%} > {pol.error_rate_max:.1%}). This run "
              f"is not a result. ***")
    return dict(daily=daily, trades=trades, equity=equity_curve, dates=dates,
                jev_holds=jev_holds[0], jev_errors=errors[0], ledger=ledger,
                error_rate=err_rate, incomplete=incomplete,
                nm_taken=nm_taken, nm_total=sum(nm_taken.values()),
                config=pol.as_record(),
                final=equity_curve[-1] if equity_curve else capital)


def memb_on(date, memb):
    usable = [d for d in memb if d <= date]
    return memb[max(usable)] if usable else set()


if __name__ == "__main__":
    import data as D
    print("loading panel ...")
    pan = D.panel([])
    idx = D.index_prices()
    print(f"  {pan['ticker'].nunique()} tickers, {len(pan):,} rows")
    print("building signals ...")
    # Membership is REQUIRED: without it RS ranks against every name that was
    # ever a member, which is the contamination repaired earlier.
    sig = S.build_signals(pan, membership=U.membership())
    sig.to_parquet(ROOT / "data" / "raw" / "signals.parquet")
    memb = U.membership()
    print("running backtest ...")
    res = run(sig, idx, memb)
    out = ROOT / "data" / "result.json"
    out.write_text(json.dumps(res, default=str))
    eq = res["equity"]
    print(f"  final equity ${eq[-1]:,.0f}  ({eq[-1]/CAPITAL-1:+.1%})  "
          f"{len(res['trades'])} trades")
