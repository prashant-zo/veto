"""Log templates, canary vs stable, from Loki.

Each line is cleaned and redacted, then its variable parts are masked, so
"order confirmed id=ab12 total=4.5" becomes "order confirmed id=<*> total=<*>".
Exact templates, not Drain clustering: Drain merges lines that differ by one
word, and a changed word is what we are looking for.
"""

import re
import time
from collections import Counter
from dataclasses import dataclass

from ..collect.loki import LogLine, Loki
from ..collect.query import quote, selector
from .injection import attack_signs
from .model import Evidence
from .redact import clean, redact

LIMIT = 5000          # loki default max lines per query
STARTUP_S = 90        # how much of a pod's first logs count as startup

LEVELS = {"DEBUG": "DEBUG", "INFO": "INFO", "WARN": "WARNING", "WARNING": "WARNING",
          "ERROR": "ERROR", "CRITICAL": "CRITICAL", "FATAL": "CRITICAL"}
BAD = {"WARNING", "ERROR", "CRITICAL"}
MAX_TEMPLATE = 300
SHOWN = 160

_LEVEL = re.compile(r"^(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\b:?\s*")
_URL = re.compile(r"https?://[^\s\"'<>]+")
_KV = re.compile(r"\b([A-Za-z_][\w.-]*)=(\"[^\"]*\"|'[^']*'|[^\s,;&\"']+)")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_HEX = re.compile(r"\b(?=[0-9a-fA-F]*\d)(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{6,}\b")
_NUM = re.compile(r"(?<![\w<.])[-+]?\d+(?:\.\d+)?(?:ms|s|%)?(?![\w>])")
_SPACE = re.compile(r"\s+")


def _mask_text(s: str) -> str:
    s = _UUID.sub("<UUID>", s)
    s = _KV.sub(lambda m: m.group(0) if m.group(2).startswith("<") else f"{m.group(1)}=<*>", s)
    s = _HEX.sub("<HEX>", s)
    return _NUM.sub("<NUM>", s)


def _mask_url(url: str) -> str:
    """Keep scheme, host, port and path words, mask ids in the path and query values."""
    base, _, query = url.partition("?")
    head, _, path = base.partition("//")[2].partition("/")
    parts = ["<NUM>" if p.isdigit() else _HEX.sub("<HEX>", _UUID.sub("<UUID>", p)) for p in path.split("/")]
    out = base.partition("//")[0] + "//" + head + ("/" + "/".join(parts) if path else "")
    if query:
        out += "?" + "&".join(f"{k.partition('=')[0]}=<*>" for k in query.split("&"))
    return out


def template_of(message: str) -> str:
    out, pos = [], 0
    for m in _URL.finditer(message):
        out.append(_mask_text(message[pos:m.start()]))
        out.append(_mask_url(m.group(0)))
        pos = m.end()
    out.append(_mask_text(message[pos:]))
    return _SPACE.sub(" ", "".join(out)).strip()[:MAX_TEMPLATE]


@dataclass(frozen=True)
class Record:
    level: str
    template: str


def records(lines: list[LogLine]) -> tuple[list[Record], Counter]:
    """Lines to records, plus what redaction removed.

    A line without a level (a traceback) folds into the record before it from
    the same pod. Only its last line is kept, the one that names the exception.
    """
    redacted: Counter = Counter()
    out: list[Record] = []
    pending: dict[str, list[str]] = {}

    def close(pod: str) -> None:
        level, head, tail = pending.pop(pod)
        out.append(Record(level, template_of(f"{head} | {tail}" if tail else head)))

    for ln in lines:
        pod = ln.labels.get("k8s_pod_name", "")
        text, counts = redact(clean(ln.line))
        redacted.update(counts)
        text = text.strip()
        if not text:
            continue
        m = _LEVEL.match(text)
        if m:
            if pod in pending:
                close(pod)
            pending[pod] = [LEVELS[m.group(1)], text[m.end():], ""]
        elif pod in pending:
            pending[pod][2] = text
        else:
            out.append(Record("UNKNOWN", template_of(text)))
    for pod in sorted(pending):
        close(pod)
    return out, redacted


@dataclass(frozen=True)
class LogStats:
    """Template counts per side. recent covers the window, total adds the pod's startup logs."""
    stable_recent: Counter
    canary_recent: Counter
    stable_total: Counter
    canary_total: Counter
    lines: dict[str, int]
    redacted: Counter
    truncated: bool


def _key(ln: LogLine) -> tuple:
    return ln.ts_ns, ln.labels.get("k8s_pod_name", ""), ln.line


def _side(recent: list[LogLine], startup: list[LogLine]) -> tuple[Counter, Counter, Counter, int]:
    seen = {_key(ln) for ln in recent}
    extra = [ln for ln in startup if _key(ln) not in seen]
    recs, red = records(recent)
    extra_recs, extra_red = records(extra)
    recent_count = Counter((r.level, r.template) for r in recs)
    total = recent_count + Counter((r.level, r.template) for r in extra_recs)
    return recent_count, total, red + extra_red, len(extra)


def build_stats(stable_recent: list[LogLine], stable_startup: list[LogLine],
                canary_recent: list[LogLine], canary_startup: list[LogLine]) -> LogStats:
    s_recent, s_total, s_red, s_extra = _side(stable_recent, stable_startup)
    c_recent, c_total, c_red, c_extra = _side(canary_recent, canary_startup)
    lines = {"stable": len(stable_recent), "stable_startup": s_extra,
             "canary": len(canary_recent), "canary_startup": c_extra}
    truncated = any(len(x) >= LIMIT for x in (stable_recent, stable_startup, canary_recent, canary_startup))
    return LogStats(s_recent, c_recent, s_total, c_total, lines, s_red + c_red, truncated)


def _fetch(loki: Loki, service: str, pod_hash: str, since_s: int, end_ns: int | None = None) -> list[LogLine]:
    logql = selector(service_name=service) + f" | rollouts_pod_template_hash={quote(pod_hash)}"
    return loki.lines(logql, since_s=since_s, limit=LIMIT, end_ns=end_ns)


def _startup(loki: Loki, service: str, pod_hash: str, started: float | None) -> list[LogLine]:
    if started is None:
        return []
    end_ns = min(int((started + STARTUP_S) * 1e9), time.time_ns())
    return _fetch(loki, service, pod_hash, STARTUP_S + 30, end_ns)


def collect_logs(loki: Loki, service: str, window_s: int,
                 stable: tuple[str, float | None], canary: tuple[str, float | None]) -> LogStats:
    """stable and canary are (pod hash, unix time its containers started)."""
    return build_stats(_fetch(loki, service, stable[0], window_s), _startup(loki, service, *stable),
                       _fetch(loki, service, canary[0], window_s), _startup(loki, service, *canary))


@dataclass(frozen=True)
class LogThresholds:
    min_requests: int = 20            # rates need this many requests on each side
    new_error_min: int = 2            # a new warning or error seen this often is hard evidence
    gone_min_per_req: float = 0.2     # a stable template this frequent per request ...
    gone_factor: float = 0.05         # ... that drops under 5 percent of it on canary is missing
    error_up_factor: float = 2.0      # a known warning or error at twice the rate per request
    error_up_min_per_req: float = 0.05
    max_items: int = 8                # per kind, most frequent first


def _short(template: str) -> str:
    return template if len(template) <= SHOWN else template[:SHOWN] + "..."


def _times(n: int) -> str:
    return "once" if n == 1 else f"{n} times"


def compare_logs(service: str, st: LogStats, stable_requests: float, canary_requests: float,
                 t: LogThresholds | None = None) -> list[Evidence]:
    t = t or LogThresholds()
    by_kind: dict[str, list[tuple[float, Evidence]]] = {}

    def add(rank: float, ev: Evidence) -> None:
        by_kind.setdefault(ev.kind, []).append((rank, ev))

    stable_seen = set(st.stable_total)
    for (level, tpl), n in st.canary_total.items():
        if (level, tpl) in stable_seen:
            continue
        detail = {"level": level, "template": tpl, "stable_count": 0, "canary_count": n}
        signs = attack_signs(tpl)
        if signs:
            add(n, Evidence("log_injection", True,
                            f"canary log text addresses the reviewer ({', '.join(signs)}), {_times(n)}: "
                            f"\"{_short(tpl)}\"", 0, n, detail | {"signs": signs}))
        elif level in BAD and n >= t.new_error_min:
            add(n, Evidence("log_new_error", True,
                            f"new {level} log on canary, {_times(n)}, never on stable: \"{_short(tpl)}\"", 0, n, detail))
        else:
            add(n, Evidence("log_new", False,
                            f"new {level} log on canary, {_times(n)}, never on stable: \"{_short(tpl)}\"", 0, n, detail))

    if min(stable_requests, canary_requests) >= t.min_requests:
        for (level, tpl), s_n in st.stable_recent.items():
            c_n = st.canary_recent.get((level, tpl), 0)
            s_per, c_per = s_n / stable_requests, c_n / canary_requests
            detail = {"level": level, "template": tpl, "stable_count": s_n, "canary_count": c_n}
            rates = f"{s_per:.2f} times per request on stable, {c_per:.2f} on canary"
            if s_per >= t.gone_min_per_req and c_per < s_per * t.gone_factor:
                add(s_n, Evidence("log_missing", False, f"{level} log {rates}: \"{_short(tpl)}\"",
                                  s_per, c_per, detail))
            elif (level in BAD and c_per > s_per * t.error_up_factor
                  and c_per - s_per >= t.error_up_min_per_req):
                add(c_n, Evidence("log_error_up", True, f"{level} log {rates}: \"{_short(tpl)}\"",
                                  s_per, c_per, detail))

    found: list[Evidence] = []
    for kind in sorted(by_kind):
        items = sorted(by_kind[kind], key=lambda x: (-x[0], x[1].summary))
        found += [ev for _, ev in items[:t.max_items]]
        if len(items) > t.max_items:
            more = len(items) - t.max_items
            found.append(Evidence(kind, items[0][1].hard, f"{more} more {kind} templates not shown", detail={"more": more}))
    return found
