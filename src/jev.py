"""Jev makes the trading judgments. This module is the boundary.

Division of labour, following TypeSafe's own guidance -- keep code in control,
give System One the narrow decisions:

  code  computes point-in-time features, sizes positions, places stops, fills
        orders, keeps the books. Nothing here is a judgment call.
  Jev   decides whether a setup is a real base, how good it is, which of
        today's candidates to prefer, and whether a wobble in an open position
        is a shakeout or a breakdown. These are the calls O'Neil made by eye.

Every `state` handed to Jev is ANONYMISED: no ticker, no date, no absolute
price. Only scale-free features. Jev is a decision model rather than a world
-knowledge model, but the point-in-time discipline in the rest of this project
is worthless if a ticker symbol and a date can reach any model, so they don't.

Answers are cached by a hash of the exact state and question set, which makes
re-runs free, offline and bit-identical.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "raw" / "jev_cache.json"

# Pin the model. `jev-latest` is an alias and can move underneath a cached
# answer without anything in the key changing.
MODEL = "jev-1.13.0"

# The cache key is a hash of the COMPLETE request -- model, state and the full
# text of every question and criterion. An earlier version hashed only a manual
# version string plus the state, so editing a prompt silently reused answers
# produced by the old one. Provenance is stored alongside each answer so a
# result can always be traced to the exact request that produced it.
CACHE_SCHEMA = 2

_client: TypeSafeClient | None = None
_cache: dict | None = None
_lock = threading.Lock()
_stats = {"hits": 0, "calls": 0, "input_tokens": 0}
_offline = False


def set_offline(flag: bool) -> None:
    """Strict replay: serve only from cache, raise on a miss. Proves a rerun
    reproduces decisions without touching the network."""
    global _offline
    _offline = flag


class JevUnavailable(RuntimeError):
    """Inference failed, or returned something the policy does not allow."""


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists() and not os.environ.get("TYPESAFE_API_KEY"):
        for line in env.read_text().splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def client() -> TypeSafeClient:
    global _client
    if _client is None:
        _load_env()
        _client = TypeSafeClient()
    return _client


def cache() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    return _cache


def save_cache() -> None:
    if _cache is not None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(_cache))


def stats() -> dict:
    return dict(_stats)


# --------------------------------------------------------------------------
# Entry: is this setup worth buying?
# --------------------------------------------------------------------------
ENTRY_QUESTIONS = {
    "proper_base": Noul(instructions=(
        "Is this a proper base breakout -- price emerging from a genuine "
        "consolidation, rather than an extended stock lurching higher or a "
        "choppy stock with no real base?")),
    "quality": Score(
        instructions="Rate this setup as a momentum entry.",
        criteria=["Poor - no real base, or badly extended",
                  "Marginal - some flaws in the structure",
                  "Acceptable - a workable base",
                  "Strong - clean base and strong leadership",
                  "Textbook - the kind of base that precedes a large advance"]),
    "follow_through": Noul(instructions=(
        "Is this breakout more likely to follow through over the coming weeks "
        "than to fail back into its base?")),
}


def describe_setup(r) -> str:
    """Anonymised, scale-free description of one breakout candidate."""
    ext = r["close"] / r["ma50"] - 1
    # Neutral opening. The earlier wording asserted "broke out of a
    # consolidation" and then asked whether a real consolidation existed,
    # which puts the answer in the question.
    return (
        f"Daily price statistics for one stock, as of today's close.\n"
        f"- Relative strength rank versus all other stocks: {int(r['rs_rating'])} of 99.\n"
        f"- It closed above the highest high of the prior "
        f"{int(r['base_len_wk'])} weeks.\n"
        f"- That consolidation was {r['base_depth']*100:.0f}% deep from high to low.\n"
        f"- Volume today was {r['vol_ratio']:.1f}x its 50-day average.\n"
        f"- Price is {(1-r['close']/r['hi52'])*100:.0f}% below its 52-week high and "
        f"{(r['close']/r['lo52']-1)*100:.0f}% above its 52-week low.\n"
        f"- Price is {ext*100:+.0f}% from its 50-day average, which sits above the "
        f"150-day, which sits above the 200-day, and the 200-day is rising.\n"
        f"- Trailing gains: {r['r3']*100:+.0f}% over 3 months, "
        f"{r['r6']*100:+.0f}% over 6 months, {r['r12']*100:+.0f}% over 12 months.\n"
        f"- Its industry group ranks in the "
        f"{_ordinal(r.get('group_pct'))} by relative strength.\n"
        f"- Average daily turnover is ${r['dollar_vol']/1e6:.0f} million.\n"
        f"- The broad market is in a {r['regime'].lower()} trend."
    )


def _ordinal(p) -> str:
    if p is None or p != p:
        return "unclassified group"
    return f"top {max(1, round((1-p)*100))}% of groups"


def _canonical(question) -> dict:
    """Everything about a question that could change the answer."""
    d = {"type": type(question).__name__}
    for attr in ("instructions", "criteria"):
        v = getattr(question, attr, None)
        if v is not None:
            d[attr] = v
    return d


def request_fingerprint(state: str, questions: dict, kind: str) -> tuple[str, dict]:
    req = {"schema": CACHE_SCHEMA, "model": MODEL, "kind": kind, "state": state,
           "questions": {k: _canonical(q) for k, q in sorted(questions.items())}}
    blob = json.dumps(req, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest(), req


def ask(state: str, questions: dict, kind: str) -> dict:
    """Cached single call keyed on the complete request.

    Returns `{question: {noul|score|choice, confidence, probabilities}}`. On an
    API failure the exception propagates -- callers must decide what an absent
    judgment means rather than silently receiving a neutral default, which
    would quietly become a trading decision nobody chose.
    """
    key, req = request_fingerprint(state, questions, kind)
    c = cache()
    hit = c.get(key)
    if hit is not None:
        _stats["hits"] += 1
        return hit["answers"]

    if _offline:
        raise JevUnavailable(f"offline replay: no cached answer for {kind}")
    r = client().system_one(state=state, questions=questions, model=MODEL)
    answers = {}
    for name, a in r.answers.items():
        rec = {}
        for f in ("noul", "score", "choice"):
            v = getattr(a, f, None)
            if v is not None:
                rec[f] = v
        conf = getattr(a, "confidence", None)
        if conf is not None:                 # Noul has none; do not invent one
            rec["confidence"] = conf
        probs = getattr(a, "probabilities", None)
        if probs:
            rec["probabilities"] = dict(probs)
        answers[name] = rec

    with _lock:
        c[key] = {
            "answers": answers,
            "request": req,
            "model_requested": MODEL,
            "model_resolved": getattr(r, "model", None),
            "usage": {"input_tokens": r.usage.input_tokens,
                      "output_tokens": r.usage.output_tokens},
            "asked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _stats["calls"] += 1
        _stats["input_tokens"] += r.usage.input_tokens
    return answers


def judge_entry(row) -> dict:
    return ask(describe_setup(row), ENTRY_QUESTIONS, "entry")


# --------------------------------------------------------------------------
# Entry v2: show Jev the price action, not a summary of it.
#
# v1 handed Jev eight summary statistics and its judgments had no predictive
# power at all (rank correlation with forward return ~0.00). The likely reason
# is that a base is a *shape* -- where the low formed, whether a handle drifted
# down on quiet volume, whether volume dried up before the break -- and none of
# that survives being reduced to depth and length. So v2 serialises the actual
# weekly bars, rebased so the breakout pivot is 100. Still no ticker, no date,
# no absolute price.
# --------------------------------------------------------------------------
SHAPE_QUESTIONS = {
    "proper_base": Noul(instructions=(
        "Reading the weekly bars: has this stock formed an orderly "
        "consolidation with supply drying up, rather than a wide, loose or "
        "erratic pattern, or a stock already extended from any such range?")),
    "quality": Score(
        instructions=(
            "Judge the price structure in these weekly bars: how tight or loose "
            "the recent range has been, how volume behaved through it and on the "
            "most recent bar, and whether the earlier trend looks likely to "
            "continue."),
        criteria=["Poor - wide and loose, or no real base",
                  "Marginal - visible flaws in the structure",
                  "Acceptable - a workable base",
                  "Strong - tight, orderly, volume confirms",
                  "Textbook - the structure that precedes a large advance"]),
    "follow_through": Noul(instructions=(
        "Over the next several weeks, is this stock more likely to advance "
        "than to fall back into its earlier range?")),
}


def describe_shape(r, bars) -> str:
    """Weekly bars rebased to pivot=100, plus the scale-free context.

    `bars` is a DataFrame of the trailing weekly OHLCV ending on the breakout
    week, oldest first, with a `vol_rel` column already expressed as a multiple
    of the 50-day average volume.
    """
    piv = r["pivot"]
    lines = []
    for i, b in enumerate(bars.itertuples(), 1):
        lines.append(
            f"  week -{len(bars)-i:<2d} open {b.open/piv*100:6.1f} "
            f"high {b.high/piv*100:6.1f} low {b.low/piv*100:6.1f} "
            f"close {b.close/piv*100:6.1f}  volume {b.vol_rel:.2f}x")
    return (
        "Weekly price bars for one stock, rebased so the highest high of the\n"
        "prior 13 weeks equals 100. The most recent bar may be a partial week.\n"
        "Volume is a multiple of its own 50-day average, so 1.00 is typical.\n\n"
        + "\n".join(lines) +
        f"\n\nContext:\n"
        f"- Relative strength rank versus all other stocks: {int(r['rs_rating'])} of 99.\n"
        f"- Price is {(1-r['close']/r['hi52'])*100:.0f}% below its 52-week high, "
        f"{(r['close']/r['lo52']-1)*100:.0f}% above its 52-week low.\n"
        f"- 50-day average is above the 150-day, above the 200-day, 200-day rising.\n"
        f"- Industry group ranks in the {_ordinal(r.get('group_pct'))}.\n"
        f"- Average daily turnover ${r['dollar_vol']/1e6:.0f} million.\n"
        f"- The broad market is in a {r['regime'].lower()} trend."
    )


def judge_shape(row, bars) -> dict:
    return ask(describe_shape(row, bars), SHAPE_QUESTIONS, "shape")


# --------------------------------------------------------------------------
# Jev in the decision loop.
#
# Division of labour, deliberately: Jev decides WHETHER to act. Code keeps the
# risk -- the 7% hard stop and the trailing stop are standing orders that fire
# regardless of what Jev thinks, because a calibrated probability is not a risk
# limit and must never be allowed to override one.
# --------------------------------------------------------------------------
# Composite scoring: four narrow judgments over the same bars, asked together
# in one call. Each is a single dimension, so "shape good but volume bad" has a
# defined answer instead of collapsing into one mixed scale. Weights and gates
# are policy and live in code (`entry_policy`), not in the model.
ENTRY_DECISION = {
    "supply": Noul(instructions=(
        "Through the consolidation before the most recent bar, did weekly "
        "volume run below its own average, and did volume then expand on the "
        "week price cleared the top of that consolidation? Answer no if volume "
        "stayed heavy through the consolidation, if the heaviest weeks were "
        "down weeks, or if the week price cleared the high was quiet.")),

    "orderly": Score(
        instructions=(
            "How orderly is the consolidation? Judge the weekly ranges: an "
            "orderly rest narrows and settles, a loose one stays wide and "
            "swings erratically."),
        criteria=[
            "Weekly ranges are wide and swing erratically from week to week "
            "with no settling anywhere in the pattern.",
            "The pattern recovers in a straight line with no quiet period, and "
            "its later weekly ranges are as wide as its earlier ones.",
            "A recognisable rest of workable depth whose weekly ranges are "
            "neither notably wide nor notably narrow.",
            "Weekly ranges narrow through the later part of the rest, with "
            "closes clustering in a tightening band.",
            "The later weeks of the rest drift in a very shallow, narrow band, "
            "each week's range small against the depth of the whole pattern.",
        ]),

    "at_pivot": Noul(instructions=(
        "Is the most recent close at or only slightly above the highest high "
        "of the weeks before it? Answer no if price has already run well above "
        "that high, so that a buyer today would be paying materially more than "
        "the breakout level.")),

    "prior_advance": Noul(instructions=(
        "Did a sustained advance come BEFORE this consolidation, so that the "
        "pattern is a rest within a rise? Answer no if the weeks leading into "
        "the pattern fell, so that the consolidation is forming at the bottom "
        "of a decline rather than pausing within an uptrend.")),
}


def entry_policy(a: dict) -> tuple[str, float]:
    """Code owns the policy. Jev supplies the four raw judgments.

    Two hard gates, both O'Neil's and both previously unenforced: do not pay up
    far beyond the breakout level, and do not buy a base that is not resting
    from an advance. Everything else is a weighted score used for ranking.
    """
    supply = float(a["supply"]["noul"])
    orderly = score_of(a, "orderly") / 4.0
    at_pivot = float(a["at_pivot"]["noul"])
    advance = float(a["prior_advance"]["noul"])

    if at_pivot < 0.5 or advance < 0.5:
        return "skip", 0.0
    if min(supply, orderly, at_pivot, advance) > 0.35:
        conviction = (0.40 * orderly + 0.25 * supply
                      + 0.20 * at_pivot + 0.15 * advance)
        return "buy", conviction
    return "unclear", 0.0


EXIT_DECISION = {
    "action": Choice(
        instructions=(
            "An open position in a William O'Neil momentum portfolio has "
            "closed below its 50-day average. O'Neil expected leaders to be "
            "shaken out on the way up: a brief undercut on lighter volume that "
            "recovers is normal and selling into it forfeits the advance. A "
            "break on heavy volume that keeps closing near the lows, after the "
            "stock is already far from its base, is distribution and the move "
            "is over. Which is this?"),
        criteria={
            "hold": ("A shakeout within an intact advance: the break is "
                     "shallow or on unremarkable volume, recent closes sit in "
                     "the upper part of their daily ranges, and the prior "
                     "trend structure is undamaged."),
            "sell": ("A breakdown: the decline is deep or persistent, recent "
                     "closes sit near the lows of their ranges on heavy "
                     "volume, and the advance no longer looks intact."),
            "unclear": ("The supplied history does not settle it, or the "
                        "signals point in opposite directions."),
        }),
}


def describe_position(r, gain_pct, days_held, peak_gain_pct, below_ma_days,
                      sessions_left, stop_distance_pct, recent=None,
                      pivot_distance_pct=None, eight_week_left=None) -> str:
    """Anonymised state of an open position under review.

    `recent` is the trailing daily sequence. Without it the question asks about
    closes near the lows and undercuts that recover while the state carries
    neither -- a day closing at its low and one closing at its high produced
    byte-identical prompts before this was added.
    """
    lines = []
    if recent is not None and len(recent):
        lines.append("\nRecent daily bars, price rebased so the entry is 100:")
        for b in recent.itertuples():
            rng = b.high - b.low
            pos = ((b.close - b.low) / rng * 100) if rng > 0 else 50.0
            lines.append(
                f"  day -{b.ago:<2d} close {b.rel:6.1f}  "
                f"range {b.lo_rel:5.1f}-{b.hi_rel:5.1f}  "
                f"closed {pos:3.0f}% up its range  volume {b.vol_rel:.2f}x")
    seq = "\n".join(lines)

    extra = ""
    if pivot_distance_pct is not None:
        extra += (f"- Price is {pivot_distance_pct:+.1f}% from the top of the "
                  f"base it broke out of.\n")
    if eight_week_left is not None:
        extra += (f"- This position gained 20% within three weeks of entry, so "
                  f"O'Neil's eight-week rule applies: {eight_week_left} "
                  f"session(s) of that hold remain.\n")

    return (
        f"An open position in a momentum portfolio has weakened.\n"
        f"- Held {days_held} trading days.\n"
        f"- Currently {gain_pct:+.1f}% from the entry price.\n"
        f"- At its best it was {peak_gain_pct:+.1f}% from entry; it has given "
        f"back {peak_gain_pct - gain_pct:.1f} points from that peak.\n"
        f"- Price is {(r['close']/r['ma50']-1)*100:+.1f}% from its 50-day "
        f"average and {(r['close']/r['ma200']-1)*100:+.1f}% from its 200-day.\n"
        f"- It has closed below the 50-day average on "
        f"{below_ma_days} consecutive day(s).\n"
        f"- Price is {(1-r['close']/r['hi52'])*100:.0f}% below its 52-week high.\n"
        f"{extra}"
        f"- Relative strength rank versus all other stocks: "
        f"{int(r['rs_rating'])} of 99.\n"
        f"- The broad market is in a {r['regime'].lower()} trend.\n"
        f"- A protective stop sits {stop_distance_pct:.1f}% below the current "
        f"price and will execute on its own if reached.\n"
        f"- The only decision available is to keep the position for up to "
        f"{sessions_left} more trading session(s); after that it is sold "
        f"regardless of this answer."
        f"{seq}"
    )


def decide_entry(row, bars) -> dict:
    return ask(describe_shape(row, bars), ENTRY_DECISION, "entry_decision_v2")


def decide_exit(row, gain_pct, days_held, peak_gain_pct, below_ma_days,
                sessions_left, stop_distance_pct, recent=None,
                pivot_distance_pct=None, eight_week_left=None) -> dict:
    state = describe_position(row, gain_pct, days_held, peak_gain_pct,
                              below_ma_days, sessions_left, stop_distance_pct,
                              recent, pivot_distance_pct, eight_week_left)
    return ask(state, EXIT_DECISION, "exit_decision")


# --- F3: a malformed or missing answer is not a decision -----------------
def choice_of(answer: dict, key: str, allowed: set[str]) -> str:
    """Pull a Choice, rejecting anything outside the declared option set."""
    try:
        v = answer[key]["choice"]
    except (KeyError, TypeError) as exc:
        raise JevUnavailable(f"{key}: no choice in response") from exc
    if v not in allowed:
        raise JevUnavailable(f"{key}: unexpected label {v!r}")
    return v


def score_of(answer: dict, key: str) -> float:
    try:
        v = float(answer[key]["score"])
    except (KeyError, TypeError, ValueError) as exc:
        raise JevUnavailable(f"{key}: no score in response") from exc
    if not (v == v) or not (0.0 <= v <= 10.0):
        raise JevUnavailable(f"{key}: score out of range ({v})")
    return v
