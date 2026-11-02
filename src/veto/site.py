"""Build site/data.json for the replay page from what is already in the repo.

Inputs: saved bundles (eval/cases), labels, the decisions make judge-all wrote
(eval/runs), eval scores and attack results (eval/results). No model calls here.
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .attacks import PAYLOADS, AttackRow
from .evaluate import Row, baseline, score
from .judge.parse import VERDICTS

MAX_REASONING = 1200


def _decision(path: Path) -> dict | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    runs = [{"model": r["model"], "seconds": r["seconds"], "verdict": r["verdict"], "attack": r.get("attack", False),
             "error": r["error"], "findings": r["findings"], "summary": r["summary"],
             "reasoning": (r.get("reasoning") or "")[:MAX_REASONING]} for r in d["runs"]]
    return {"verdict": d["verdict"], "stage": d["stage"], "ceiling": d["ceiling"], "reasons": d["reasons"],
            "summary": d["summary"], "bundle_hash": d["bundle_hash"], "runs": runs}


def _case(path: Path, labels: dict, runs_dir: Path) -> dict:
    b = json.loads(path.read_text())
    label = labels.get(path.stem, {})
    intent = b.get("intent")
    pr = None
    if intent:
        pr = {"number": intent["pr"], "title": intent["title"], "body": intent["body"], "commits": intent["commits"],
              "files": [{"path": f["path"], "status": f["status"], "patch": f["patch"]} for f in intent["files"]]}
    decision = _decision(runs_dir / path.name)
    if decision and decision["bundle_hash"] != b["hash"]:
        decision = None     # judged on another bundle, do not mix them
    return {
        "case": path.stem, "expected": label.get("expected"), "why": label.get("why", ""),
        "baseline": baseline(b), "canary_tag": b["rollout"]["canary_tag"], "service": b["rollout"]["service"],
        "window": b["rollout"]["window"], "created_at": b["created_at"], "bundle_hash": b["hash"],
        "stable": b["stable"], "canary": b["canary"], "traffic": b["traffic"], "pr": pr,
        "evidence": [{"id": e["id"], "kind": e["kind"], "hard": e["hard"], "summary": e["summary"]}
                     for e in b["evidence"]],
        "decision": decision,
    }


def _scores(path: Path) -> dict | None:
    if not path.exists():
        return None
    rows = [Row(**r) for r in json.loads(path.read_text())]
    return {"veto": score(rows, "veto"), "baseline": score(rows, "baseline"),
            "repeats": max((len(r.veto) for r in rows), default=0)}


def _attacks(path: Path) -> dict | None:
    if not path.exists():
        return None
    rows = [AttackRow(**r) for r in json.loads(path.read_text())]
    asked = [r for r in rows if r.runs]
    unflagged = [r for r in rows if r.caught == "no"]
    return {
        "count": len(rows),
        "floor": sum(r.caught == "floor" for r in rows),
        "flagged": sum(r.caught == "flagged" for r in rows),
        "unflagged": len(unflagged),
        "called_out": sum(r.attack_runs == len(r.runs) > 0 for r in unflagged),
        "runs": sum(len(r.runs) for r in asked),
        "fooled_runs": sum(r.fooled_runs for r in asked),
        "looser": sum(VERDICTS.index(r.verdict) > VERDICTS.index(r.expected) for r in rows),
        "shipped": sum(r.shipped for r in rows),
        "payloads": PAYLOADS,
        "rows": [asdict(r) for r in rows],
    }


def build(root: Path, model_slug: str = "muse-spark-open-1026", fallback_slug: str = "muse-spark-1.3") -> dict:
    labels = json.loads((root / "eval" / "labels.json").read_text())
    results = root / "eval" / "results"
    return {
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model_slug,
        "cases": [_case(p, labels, root / "eval" / "runs") for p in sorted((root / "eval" / "cases").glob("*.json"))],
        "eval": {"primary": _scores(results / f"{model_slug}.json"), "fallback": _scores(results / f"{fallback_slug}.json")},
        "attacks": _attacks(results / f"attacks-{model_slug}.json"),
    }


def write(root: Path, out: Path) -> dict:
    data = build(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=True) + "\n")
    return data
