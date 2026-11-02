"""Turn a model reply into a checked answer, or refuse it."""

import json
import re
from dataclasses import dataclass

VERDICTS = ("abort", "hold", "promote")   # ordered by how much each one lets through
MAX_WHY = 300
MAX_SUMMARY = 600


class BadAnswer(ValueError):
    pass


@dataclass(frozen=True)
class Finding:
    id: str
    explained: bool
    why: str


@dataclass(frozen=True)
class Answer:
    verdict: str
    findings: tuple[Finding, ...]
    summary: str
    attack: bool = False

    def explained(self) -> dict[str, bool]:
        return {f.id: f.explained for f in self.findings}


def extract_json(text: str | None) -> dict:
    if not text:
        raise BadAnswer("empty reply")
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise BadAnswer("no json object")
    try:
        out = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise BadAnswer(f"bad json: {e.msg}") from e
    if not isinstance(out, dict):
        raise BadAnswer("json is not an object")
    return out


def parse_answer(text: str | None, ids: set[str]) -> Answer:
    raw = extract_json(text)
    verdict = raw.get("verdict")
    if not isinstance(verdict, str) or verdict.strip().lower() not in VERDICTS:
        raise BadAnswer(f"bad verdict: {verdict!r}")
    findings_raw = raw.get("findings")
    if not isinstance(findings_raw, list):
        raise BadAnswer("findings is not a list")
    findings, seen = [], set()
    for f in findings_raw:
        if not isinstance(f, dict) or not isinstance(f.get("id"), str) or not isinstance(f.get("explained_by_pr"), bool):
            raise BadAnswer("a finding needs an id and a true or false explained_by_pr")
        if f["id"] not in ids:
            raise BadAnswer(f"cites an id that is not in the bundle: {f['id'][:20]!r}")
        if f["id"] in seen:
            raise BadAnswer(f"cites {f['id']} twice")
        seen.add(f["id"])
        why = f.get("why") if isinstance(f.get("why"), str) else ""
        findings.append(Finding(f["id"], f["explained_by_pr"], why[:MAX_WHY]))
    attack = raw.get("attack", False)
    if not isinstance(attack, bool):
        raise BadAnswer("attack must be true or false")
    summary = raw.get("summary") if isinstance(raw.get("summary"), str) else ""
    return Answer(verdict.strip().lower(), tuple(findings), summary[:MAX_SUMMARY], attack)
