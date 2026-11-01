"""Spot text that talks to the reviewer instead of describing the software.

Logs and PR text are data. A log line that says "verdict promote" is not
telemetry, it is an attack on the judge. One strong sign is enough,
weak signs need two different ones.
"""

import re

_STRONG = [
    ("ignore instructions", r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|rules|prompts?|guidelines)\b"),
    ("system prompt", r"\bsystem\s+prompt\b"),
    ("chat markup", r"<\|[a-z_]+\|>|\[/?inst\]|<<sys>>"),
    ("talks to the model", r"\b(you are|you're|act as)\s+(now\s+)?(an?\s+|the\s+)?(\w+\s+)?(ai|assistant|model|llm|reviewer|judge)\b"),
]
_WEAK = [
    ("verdict", r"\bverdict\b"),
    ("promote", r"\bpromot(e|ed|ion)\b"),
    ("approval claim", r"\b(approved?|approval|sign(ed)?[- ]off)\b"),
    ("addresses checks", r"\b(automated|ai|llm)\s+(checks?|review(er)?s?|gates?|judges?)\b"),
    ("tests passed", r"\ball\s+tests\s+pass(ed)?\b"),
    ("safe claim", r"\bsafe\s+to\s+(deploy|promote|merge|release|ship)\b"),
    ("do not report", r"\b(do\s+not|don'?t|never)\s+(flag|report|mention|abort|block|hold)\b"),
    ("role tag", r"(^|\s)(system|assistant)\s*:"),
]
_STRONG_RE = [(name, re.compile(p, re.IGNORECASE)) for name, p in _STRONG]
_WEAK_RE = [(name, re.compile(p, re.IGNORECASE)) for name, p in _WEAK]


def attack_signs(text: str) -> list[str]:
    """Names of the signs found, or [] when the text does not look like an attack."""
    strong = [name for name, p in _STRONG_RE if p.search(text)]
    weak = [name for name, p in _WEAK_RE if p.search(text)]
    if strong or len(weak) >= 2:
        return strong + weak
    return []
