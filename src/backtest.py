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

import macro as MAC
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
                 "below_ma_days")

    def __init__(self, ticker, shares, entry, entry_date, entry_idx):
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


def index_by_date(sig: pd.DataFrame) -> dict:
    """date -> rows indexed by ticker. Built once and reused across runs."""
    return {d: g.set_index("ticker") for d, g in sig.groupby("date")}


def run(sig: pd.DataFrame, idx: pd.DataFrame, memb: dict, *,
        start: str | None = None, end: str | None = None,
        capital: float | None = None, by_date: dict | None = None,
        feat: pd.DataFrame | None = None) -> dict:
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
    positions: dict[str, Position] = {}
    pending_buys: list[str] = []
    pending_sells: list[tuple[str, str]] = []
    equity_curve, trades, daily = [], [], []

    for i, today in enumerate(dates):
        rows = by_date.get(today)
        if rows is None:
            continue
        reg = regime.loc[today] if today in regime.index else None
        regime_name = reg["regime"] if reg is not None else "YELLOW"
        max_pos = int(reg["max_positions"]) if reg is not None else S.MAX_POSITIONS
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
        for tkr in pending_buys:
            if tkr in positions or len(positions) >= max_pos or tkr not in rows.index:
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
            positions[tkr] = Position(tkr, shares, fill, today, i)
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
                atr = px(tkr, "atr20")
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
            if p.below_ma_days >= need:
                pending_sells.append((tkr, f"broke 50dma ({regime_name})"))

        sell_set = {t for t, _ in pending_sells}
        open_slots = max_pos - (len(positions) - len(sell_set))
        n_cands = 0
        if open_slots > 0 and regime_name != "RED":
            live = set(memb_on(today, memb))
            cands = rows[rows["buyable"].fillna(False)]
            cands = cands[cands.index.isin(live) & ~cands.index.isin(positions)]
            if S.GROUP_MIN_PCT and "group_pct" in cands.columns:
                # Buy leaders of leading groups. An unclassified name passes
                # rather than being dropped: the gaps are Nasdaq-only listings,
                # heavily semis, so excluding them would bias against exactly
                # the groups this filter exists to find.
                gp = cands["group_pct"]
                cands = cands[gp.isna() | (gp >= S.GROUP_MIN_PCT)]
            n_cands = len(cands)
            # rs_rating is rounded to whole numbers, so ties are common. Break
            # them on ticker rather than on row order, otherwise the result
            # depends on how the signal file happened to be written.
            pending_buys = (cands.sort_values("rs_rating", ascending=False,
                                              kind="mergesort")
                            .sort_index(kind="mergesort")
                            .sort_values("rs_rating", ascending=False,
                                         kind="mergesort")
                            .index[:open_slots].tolist())

        daily.append(dict(
            date=str(today.date()), equity=round(equity, 2), cash=round(cash, 2),
            regime=regime_name, slots=max_pos, open_slots=max(0, open_slots),
            n_cands=n_cands,
            positions=[dict(t=t, sh=p.shares, entry=round(p.entry, 2),
                            px=round(px(t, "close"), 2),
                            pct=round((px(t, "close") / p.entry - 1) * 100, 1),
                            val=round(p.shares * px(t, "close"), 0))
                       for t, p in sorted(positions.items())
                       if np.isfinite(px(t, "close"))],
            trades=todays_trades))

    return dict(daily=daily, trades=trades, equity=equity_curve, dates=dates,
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
    sig = S.build_signals(pan)
    sig.to_parquet(ROOT / "data" / "raw" / "signals.parquet")
    memb = U.membership()
    print("running backtest ...")
    res = run(sig, idx, memb)
    out = ROOT / "data" / "result.json"
    out.write_text(json.dumps(res, default=str))
    eq = res["equity"]
    print(f"  final equity ${eq[-1]:,.0f}  ({eq[-1]/CAPITAL-1:+.1%})  "
          f"{len(res['trades'])} trades")
