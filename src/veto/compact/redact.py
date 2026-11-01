"""Scrub text before it can leave the cluster.

clean() drops terminal escapes and invisible characters, redact() swaps
secrets and personal data for placeholders and counts what it swapped.
"""

import re
import unicodedata
from collections import Counter

MAX_LEN = 2000

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_HIDDEN = [(0x00AD, 0x00AD), (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x2064), (0x2066, 0x2069),
           (0xFEFF, 0xFEFF)]  # soft hyphen, zero width, bidi controls, byte order mark
_INVISIBLE = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in _HIDDEN) + "]")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

# specific token shapes first, generic ones last
_RULES = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.DOTALL),
     "<PRIVATE_KEY>"),
    ("jwt", re.compile(r"\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}"), "<JWT>"),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "<AWS_KEY>"),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_\w{30,})"), "<GITHUB_TOKEN>"),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "<SLACK_TOKEN>"),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "<API_KEY>"),
    ("bearer", re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 <TOKEN>"),
    ("url_password", re.compile(r"(://)[^/\s:@]+:[^/\s@]+@"), r"\1<CREDENTIALS>@"),
    ("secret_value", re.compile(
        r"(?i)\b([\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|credential)[\w.-]*)"
        r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"), r"\1\2<SECRET>"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<EMAIL>"),
    ("ip", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<IP>"),
    ("blob", re.compile(r"\b(?=[A-Za-z_-]*\d)[A-Za-z0-9_-]{32,}\b"), "<BLOB>"),
]


def clean(text: str, limit: int | None = MAX_LEN) -> str:
    """limit is for log lines, PR text is cut later with a visible marker."""
    text = unicodedata.normalize("NFKC", text)
    text = _ANSI.sub("", text)
    text = _INVISIBLE.sub("", text)
    text = _CONTROL.sub(" ", text)
    return text[:limit] if limit else text


def redact(text: str) -> tuple[str, Counter]:
    counts: Counter = Counter()
    for name, pattern, repl in _RULES:
        text, n = pattern.subn(repl, text)
        if n:
            counts[name] += n
    return text, counts
