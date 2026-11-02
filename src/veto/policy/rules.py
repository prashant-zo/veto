"""The rules that decide, around the model.

floor:   evidence bad enough to abort before the model runs.
person:  no trustworthy PR to compare against, hold before the model runs.
ceiling: the most the release can get. Any hard evidence caps it at hold.
combine: the model answers checked against the bundle, then capped.
The model can make a verdict stricter, never looser than the ceiling.
"""

import re
from dataclasses import dataclass

from ..compact.injection import STRONG_NAMES
from ..judge.parse import VERDICTS, Answer

ATTACKS = ("log_injection", "pr_injection")
NO_INTENT = ("intent_missing", "intent_unavailable", "intent_sha_mismatch")
CODE_BACKED = {"log_new": "+", "log_missing": "-"}   # soft log items must show up in added or removed lines


@dataclass(frozen=True)
class Rules:
    runs: int = 3                     # model runs per decision, all must agree
    abort_error_jump: float = 0.10    # canary error ratio this far over stable aborts before the model
    attack_signs: int = 3             # this many attack signs, or one strong one, aborts before the model


def stricter(a: str, b: str) -> str:
    return a if VERDICTS.index(a) <= VERDICTS.index(b) else b


def floor(bundle: dict, rules: Rules) -> list[str]:
    reasons = []
    for e in bundle["evidence"]:
        if e["kind"] == "error_rate_up" and (e["canary"] or 0) - (e["stable"] or 0) >= rules.abort_error_jump:
            reasons.append(f"{e['id']}: error ratio {e['stable']:.1%} on stable, {e['canary']:.1%} on canary, "
                           f"past the {rules.abort_error_jump:.0%} abort line")
        if e["kind"] in ATTACKS:
            signs = set(e["detail"].get("signs", []))
            if signs & STRONG_NAMES or len(signs) >= rules.attack_signs:
                reasons.append(f"{e['id']}: {e['kind']}, the release carries text telling the reviewer to approve it")
    return reasons


def needs_person(bundle: dict) -> list[str]:
    """Without the PR the change was made under, there is nothing for the model to check."""
    return [f"{e['id']}: {e['kind']}, there is no trustworthy PR to compare the canary against"
            for e in bundle["evidence"] if e["kind"] in NO_INTENT]


def ceiling(bundle: dict) -> tuple[str, list[str]]:
    reasons = [f"{e['id']}: {e['kind']} is hard evidence" for e in bundle["evidence"] if e["hard"]]
    if not bundle["traffic"]["enough_to_promote"]:
        reasons.append("not enough traffic to promote")
    if bundle["traffic"]["logs_partial"]:
        reasons.append("log counts are partial")
    if bundle.get("intent") is None and not any(e["kind"].startswith("intent_") for e in bundle["evidence"]):
        reasons.append("no pull request in the bundle")
    return ("hold" if reasons else "promote"), reasons


_PLACEHOLDER = re.compile(r"<[A-Z_*]+>")
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_COMMENT = ("#", "//", "/*", "*", "--")
_NOT_SOURCE = re.compile(r"(^|/)(tests?|docs?)/|(^|/)test_[^/]*$|_test\.\w+$|\.(md|rst|txt)$")


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(_PLACEHOLDER.sub(" ", text))]


def changed_code(intent: dict | None, sign: str) -> list[str]:
    """Added (+) or removed (-) lines in source files, comments left out."""
    out = []
    for f in (intent or {}).get("files", []):
        if _NOT_SOURCE.search(f["path"]):
            continue
        for ln in (f["patch"] or "").splitlines():
            if ln.startswith(sign) and not ln.startswith(sign * 3):
                code = ln[1:].strip()
                if code and not code.startswith(_COMMENT):
                    out.append(code)
    return out


def code_backed(item: dict, intent: dict | None) -> bool:
    """Every word of the log template but one (the logger name) must appear in one changed line."""
    words = _words(item["detail"].get("template", ""))
    if len(words) < 2:
        return False
    need = max(2, len(words) - 1)
    for line in changed_code(intent, CODE_BACKED[item["kind"]]):
        have = set(_words(line))
        if sum(w in have for w in words) >= need:
            return True
    return False


def combine(bundle: dict, answers: list[Answer | None], errors: list[str], cap: str) -> tuple[str, list[str]]:
    if errors:
        return "hold", [f"model run failed: {e}" for e in errors]
    verdicts = [a.verdict for a in answers]
    if len(set(verdicts)) != 1:
        return "hold", [f"model runs disagree: {', '.join(verdicts)}"]
    verdict, reasons = verdicts[0], []
    ids = [e["id"] for e in bundle["evidence"]]

    # the model is a second attack detector: one run seeing an attack stops a promote,
    # all runs seeing it lets an abort stand even with every evidence item explained
    if verdict == "promote" and any(a.attack for a in answers):
        return "hold", ["a model run found text in the bundle trying to steer the answer"]
    attack = all(a.attack for a in answers)
    if attack:
        reasons.append("every model run found text in the bundle trying to steer the answer")
    elif verdict == "abort" and not any(not ok for a in answers for ok in a.explained().values()):
        return "hold", ["model said abort but marked no evidence as unexplained"]

    if verdict == "promote":
        for a in answers:
            got = a.explained()
            missing = [i for i in ids if not got.get(i)]
            if missing:
                return "hold", [f"model said promote but did not explain {', '.join(missing)}"]
        for e in bundle["evidence"]:
            if e["kind"] in CODE_BACKED and not code_backed(e, bundle.get("intent")):
                reasons.append(f"{e['id']}: {e['kind']} text is not in the PR diff")
        if reasons:
            return "hold", reasons

    final = stricter(verdict, cap)
    if final != verdict:
        reasons.append(f"model said {verdict}, capped at {cap}")
    return final, reasons
