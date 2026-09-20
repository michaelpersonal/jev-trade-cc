"""Labeller A: a deliberately simple, transparent rule.

This exists to be a real baseline. If Jev cannot beat a regex on this task,
that is the finding. Written against `rubric.md` before any Jev answer existed.
"""
from __future__ import annotations

import re

WITHDRAW = r"(withdraw\w*|suspend\w*|rescind\w*|not\s+reaffirm\w*|no\s+longer\s+(?:be\s+)?(?:reaffirm\w*|appl\w*|in\s+effect))"
GUIDANCE = r"(guidance|outlook|forecast|projections?|targets?)"
# The sharpest distractor: non-reliance on past financials is not a withdrawal
# of forward guidance.
FINANCIALS = r"(financial\s+statements?|previously\s+issued\s+financial|interim\s+financial|balance\s+sheets?|audit\s+report)"
HYPOTHETICAL = r"(may\s+(?:be\s+required\s+to\s+)?withdraw|could\s+withdraw|risk\s+factors?|if\s+we\s+(?:were\s+)?to\s+withdraw)"


def label(passage: str) -> tuple[str, str]:
    """Return (label, reason) where label is yes / no / unclear."""
    t = re.sub(r"\s+", " ", passage.lower())

    hits = []
    for m in re.finditer(WITHDRAW, t):
        window = t[max(0, m.start() - 160): m.end() + 160]
        if re.search(GUIDANCE, window):
            hits.append((m.group(0), window))

    if not hits:
        return "no", "no withdrawal verb near a guidance noun"

    for verb, window in hits:
        if re.search(FINANCIALS, window) and not re.search(
                r"(guidance|outlook)\s+(is|are|has|have|will)", window):
            continue                     # non-reliance on statements, not guidance
        if re.search(HYPOTHETICAL, window):
            continue                     # conditional or risk-factor language
        return "yes", f"'{verb}' within 160 chars of a guidance noun"

    return "no", "withdrawal language refers to financials, or is hypothetical"
