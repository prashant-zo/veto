"""The evidence bundle: everything the judge sees, with stable ids and a hash.

Ids are M (metrics and call edges), L (logs) and P (pull request).
The hash covers everything except the time it was made, so a verdict can
always be tied to the exact bundle it was given.
"""

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime

from . import config
from .collect.github import GitHub, GitHubError, Intent
from .collect.kube import tag_of
from .compact.intent import intent_doc, intent_evidence
from .compact.metrics import window_seconds
from .compact.model import Evidence, SideStats
from .evidence import Gathered, gather

SCHEMA = "veto.bundle/v1"


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def _prefix(kind: str) -> str:
    if kind.startswith("log_"):
        return "L"
    if kind.startswith(("intent_", "pr_")):
        return "P"
    return "M"


def with_ids(found: list[Evidence]) -> list[dict]:
    seen: Counter = Counter()
    out = []
    for e in found:
        p = _prefix(e.kind)
        seen[p] += 1
        out.append({"id": f"{p}{seen[p]}", "kind": e.kind, "hard": e.hard, "summary": e.summary,
                    "stable": _r(e.stable), "canary": _r(e.canary), "detail": e.detail})
    return out


def _side(st: SideStats, image: str, requests: float) -> dict:
    per_req = {d: _r(e.rps / st.rps) if st.rps else 0.0 for d, e in sorted(st.edges.items())}
    return {"hash": st.hash, "image": image, "requests": round(requests), "error_ratio": _r(st.err_ratio),
            "p99_ms": _r(st.p99_ms), "calls_per_request": per_req}


def bundle_hash(bundle: dict) -> str:
    body = {k: v for k, v in bundle.items() if k not in ("hash", "created_at")}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def build(g: Gathered, intent: Intent | None, intent_error: str | None, now: datetime | None = None) -> dict:
    ws = window_seconds(g.window)
    tag = tag_of(g.canary_image)
    redacted = Counter(g.logs.redacted)
    doc = intent_doc(intent, redacted) if intent else None
    found = list(g.found) + intent_evidence(tag, intent, intent_error)
    bundle = {
        "schema": SCHEMA,
        "created_at": (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rollout": {"namespace": g.namespace, "service": g.service, "window": g.window, "canary_tag": tag},
        "stable": _side(g.stable, g.stable_image, g.stable.rps * ws),
        "canary": _side(g.canary, g.canary_image, g.canary.rps * ws),
        "traffic": {"enough_to_promote": g.enough, "logs_partial": g.logs.truncated},
        "intent": doc,
        "evidence": with_ids(found),
        "redacted": dict(sorted(redacted.items())),
    }
    bundle["hash"] = bundle_hash(bundle)
    return bundle


def collect(namespace: str, service: str, window: str) -> dict | None:
    """Live bundle for a running canary, None when there is none."""
    s = config.load()
    g = gather(s, namespace, service, window)
    if g is None:
        return None
    try:
        intent, error = GitHub(s.github_repo, s.github_token, s.http_timeout).intent_for_tag(tag_of(g.canary_image)), None
    except GitHubError as e:
        intent, error = None, str(e)
    return build(g, intent, error)
