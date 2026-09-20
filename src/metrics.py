"""Performance statistics for the strategy and its benchmark."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _series(equity: list[float], dates: list) -> pd.Series:
    return pd.Series(equity, index=pd.to_datetime([str(d) for d in dates]))


def drawdown(eq: pd.Series) -> pd.Series:
    return eq / eq.cummax() - 1.0


def summarize(equity: list[float], dates: list, label: str) -> dict:
    eq = _series(equity, dates)
    rets = eq.pct_change().dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    total = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    dd = drawdown(eq)
    downside = rets[rets < 0].std() * np.sqrt(TRADING_DAYS)
    return dict(
        label=label,
        start=round(float(eq.iloc[0]), 2),
        final=round(float(eq.iloc[-1]), 2),
        total_return=round(float(total) * 100, 2),
        cagr=round(float(cagr) * 100, 2),
        vol=round(float(vol) * 100, 2),
        sharpe=round(float(cagr / vol), 2) if vol else None,
        sortino=round(float(cagr / downside), 2) if downside else None,
        max_dd=round(float(dd.min()) * 100, 2),
        max_dd_date=str(dd.idxmin().date()),
        best_day=round(float(rets.max()) * 100, 2),
        worst_day=round(float(rets.min()) * 100, 2),
        years=round(years, 2),
    )


def trade_stats(trades: list[dict]) -> dict:
    sells = [t for t in trades if t["side"] == "SELL"]
    if not sells:
        return {}
    pnl = np.array([t["pnl"] for t in sells])
    pct = np.array([t["pct"] for t in sells])
    held = np.array([t["held"] for t in sells])
    wins, losses = pnl > 0, pnl <= 0
    gross_win = pnl[wins].sum()
    gross_loss = -pnl[losses].sum()
    reasons: dict[str, int] = {}
    for t in sells:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    best = max(sells, key=lambda t: t["pct"])
    worst = min(sells, key=lambda t: t["pct"])
    return dict(
        n_trades=len(trades),
        n_closed=len(sells),
        win_rate=round(float(wins.mean()) * 100, 1),
        avg_win=round(float(pct[wins].mean()), 2) if wins.any() else 0.0,
        avg_loss=round(float(pct[losses].mean()), 2) if losses.any() else 0.0,
        avg_hold=round(float(held.mean()), 1),
        avg_hold_win=round(float(held[wins].mean()), 1) if wins.any() else 0.0,
        avg_hold_loss=round(float(held[losses].mean()), 1) if losses.any() else 0.0,
        profit_factor=round(float(gross_win / gross_loss), 2) if gross_loss else None,
        expectancy=round(float(pct.mean()), 2),
        exit_reasons=reasons,
        best=dict(ticker=best["ticker"], pct=best["pct"], pnl=best["pnl"],
                  date=best["date"], held=best["held"]),
        worst=dict(ticker=worst["ticker"], pct=worst["pct"], pnl=worst["pnl"],
                   date=worst["date"], held=worst["held"]),
    )


def benchmark(idx: pd.DataFrame, dates: list, capital: float) -> list[float]:
    """Buy-and-hold S&P 500 with the same starting capital, same dates."""
    c = idx["Close"].reindex(pd.to_datetime([str(d) for d in dates])).ffill()
    return [round(float(capital * x / c.iloc[0]), 2) for x in c]
