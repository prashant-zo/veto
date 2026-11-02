"""Score Veto against the expected verdicts, next to a metrics-only baseline.

The baseline is what a usual canary analysis checks: error rate and latency,
nothing else. A grade is right, stricter (safe, but a person has to step in)
or looser (let through more than it should). shipped counts promotes that should not have happened.
"""

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .decide import decide
from .judge.model import Reply
from .judge.parse import VERDICTS


@dataclass
class Row:
    case: str
    expected: str | None
    veto: list[str]
    stage: str
    baseline: str
    seconds: float
    run_verdicts: list[list[str | None]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def baseline(bundle: dict, error_jump: float = 0.01, latency_factor: float = 1.5, latency_min_ms: float = 50) -> str:
    s, c = bundle["stable"], bundle["canary"]
    if c["error_ratio"] - s["error_ratio"] > error_jump:
        return "abort"
    if s["p99_ms"] and c["p99_ms"] and c["p99_ms"] > s["p99_ms"] * latency_factor \
            and c["p99_ms"] - s["p99_ms"] > latency_min_ms:
        return "abort"
    return "promote"


def grade(expected: str | None, got: str) -> str:
    if expected is None:
        return "held out"
    diff = VERDICTS.index(got) - VERDICTS.index(expected)
    return "right" if diff == 0 else ("looser" if diff > 0 else "stricter")


def run(cases: Path, labels: dict, ask: Callable[[list[dict]], Reply], repeat: int = 1) -> list[Row]:
    rows = []
    for path in sorted(cases.glob("*.json")):
        bundle = json.loads(path.read_text())
        label = labels.get(path.stem, {})
        verdicts, runs, seconds, stage, reasons = [], [], 0.0, "", []
        for _ in range(repeat):
            d = decide(bundle, ask)
            verdicts.append(d.verdict)
            runs.append([r.verdict for r in d.runs])
            seconds = max(seconds, max((r.seconds for r in d.runs), default=0.0))
            stage, reasons = d.stage, d.reasons
        rows.append(Row(path.stem, label.get("expected"), verdicts, stage, baseline(bundle), seconds, runs, reasons))
    return rows


def score(rows: list[Row], who: str) -> dict[str, int]:
    out = {"right": 0, "stricter": 0, "looser": 0, "shipped": 0, "scored": 0}
    for row in rows:
        if row.expected is None:
            continue
        got = row.veto if who == "veto" else [row.baseline] * len(row.veto)
        for v in got:
            out[grade(row.expected, v)] += 1
            out["shipped"] += v == "promote" and row.expected != "promote"
            out["scored"] += 1
    return out


def report(rows: list[Row], model: str) -> str:
    lines = [f"# eval: {model}", "",
             "| case | expected | veto | decided by | baseline | slowest run |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        veto = ", ".join(f"{v} ({grade(r.expected, v)})" for v in r.veto)
        base = f"{r.baseline} ({grade(r.expected, r.baseline)})"
        slow = f"{r.seconds:.1f}s" if r.stage == "model" else "-"
        lines.append(f"| {r.case} | {r.expected or 'held out'} | {veto} | {r.stage} | {base} | {slow} |")
    for who in ("veto", "baseline"):
        s = score(rows, who)
        lines.append("")
        lines.append(f"{who}: {s['right']} of {s['scored']} right, {s['stricter']} stricter, "
                     f"{s['looser']} looser, {s['shipped']} shipped that should not have")
    return "\n".join(lines) + "\n"


def save(rows: list[Row], model: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = model.rsplit("/", 1)[-1]
    (out_dir / f"{slug}.json").write_text(json.dumps([asdict(r) for r in rows], indent=2) + "\n")
    md = out_dir / f"{slug}.md"
    md.write_text(report(rows, model))
    return md


def rescore(results: Path, labels: dict) -> list[Row]:
    """Apply labels that arrived later to saved results, without asking the model again.

    This is how a blind PR gets scored: the verdicts stay exactly what the code decided
    before anyone knew the answer.
    """
    rows = [Row(**r) for r in json.loads(results.read_text())]
    for row in rows:
        row.expected = labels.get(row.case, {}).get("expected")
    return rows
