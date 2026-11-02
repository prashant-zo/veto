"""What the Veto page shows for one release, made from a bundle and a decision.

The replay site (site.py) and the live page Veto serves (serve/app.py) both
use this, so one page reads the same shape from either.
"""

import re

from .evaluate import baseline

MAX_REASONING = 1200
_PR = re.compile(r"^(pr-\d+)-")


def short_tag(tag: str | None) -> str:
    """pr-7-be303b7 becomes pr-7, anything else stays as it is."""
    if not tag:
        return "no tag"
    m = _PR.match(tag)
    return m.group(1) if m else tag


def decision_view(d: dict) -> dict:
    runs = [{"model": r["model"], "seconds": r["seconds"], "verdict": r["verdict"], "attack": r.get("attack", False),
             "error": r["error"], "findings": r["findings"], "summary": r["summary"],
             "reasoning": (r.get("reasoning") or "")[:MAX_REASONING]} for r in d["runs"]]
    return {"verdict": d["verdict"], "stage": d["stage"], "ceiling": d["ceiling"], "reasons": d["reasons"],
            "summary": d["summary"], "bundle_hash": d["bundle_hash"], "runs": runs}


def case_view(name: str, b: dict, decision: dict | None, label: dict | None = None) -> dict:
    label = label or {}
    intent = b.get("intent")
    pr = None
    if intent:
        pr = {"number": intent["pr"], "title": intent["title"], "body": intent["body"], "commits": intent["commits"],
              "files": [{"path": f["path"], "status": f["status"], "patch": f["patch"]} for f in intent["files"]]}
    return {
        "case": name, "expected": label.get("expected"), "why": label.get("why", ""),
        "baseline": baseline(b), "canary_tag": b["rollout"]["canary_tag"], "service": b["rollout"]["service"],
        "window": b["rollout"]["window"], "created_at": b["created_at"], "bundle_hash": b["hash"],
        "stable": b["stable"], "canary": b["canary"], "traffic": b["traffic"], "pr": pr,
        "evidence": [{"id": e["id"], "kind": e["kind"], "hard": e["hard"], "summary": e["summary"]}
                     for e in b["evidence"]],
        "decision": decision,
    }
