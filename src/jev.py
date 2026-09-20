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
