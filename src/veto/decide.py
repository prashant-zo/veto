"""One decision for one bundle: floor, ceiling, three model runs, checks."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from .bundle import SCHEMA, bundle_hash
from .judge.model import Reply
from .judge.parse import Answer, BadAnswer, parse_answer
from .judge.prompt import messages
from .policy.rules import Rules, ceiling, combine, floor, needs_person

MAX_REASONING = 4000


class BadBundle(ValueError):
    pass


@dataclass
class Run:
    label: str
    model: str
    seconds: float
    verdict: str | None = None
    error: str | None = None
    findings: list[dict] = field(default_factory=list)
    summary: str = ""
    reasoning: str = ""


@dataclass
class Decision:
    verdict: str
    service: str
    canary_tag: str
    bundle_hash: str
    stage: str              # floor or policy: decided before the model, model: after it
    ceiling: str
    reasons: list[str]
    summary: str
    runs: list[Run]

    def to_dict(self) -> dict:
        return asdict(self)


def check(bundle: dict) -> None:
    if bundle.get("schema") != SCHEMA:
        raise BadBundle(f"unknown bundle schema {bundle.get('schema')!r}")
    if bundle_hash(bundle) != bundle.get("hash"):
        raise BadBundle("bundle hash does not match its content, refusing to judge it")


def decide(bundle: dict, ask: Callable[[list[dict]], Reply], rules: Rules | None = None) -> Decision:
    rules = rules or Rules()
    check(bundle)
    base = {"service": bundle["rollout"]["service"], "canary_tag": bundle["rollout"]["canary_tag"],
            "bundle_hash": bundle["hash"]}

    stop = floor(bundle, rules)
    if stop:
        more = f" (and {len(stop) - 1} more)" if len(stop) > 1 else ""
        return Decision("abort", stage="floor", ceiling="abort", reasons=stop,
                        summary=f"Aborted before the model ran. {stop[0]}{more}.", runs=[], **base)

    person = needs_person(bundle)
    if person:
        return Decision("hold", stage="policy", ceiling="hold", reasons=person,
                        summary=f"Held before the model ran. {person[0]}. A person has to say what this release is for.",
                        runs=[], **base)

    cap, cap_reasons = ceiling(bundle)
    msgs = messages(bundle)
    with ThreadPoolExecutor(rules.runs) as pool:
        replies = list(pool.map(lambda _: ask(msgs), range(rules.runs)))

    ids = {e["id"] for e in bundle["evidence"]}
    runs, answers, errors = [], [], []
    for n, r in enumerate(replies, 1):
        run = Run(r.label, r.model, r.seconds, reasoning=(r.reasoning or "")[:MAX_REASONING])
        try:
            if r.error:
                raise BadAnswer(r.error)
            a: Answer = parse_answer(r.content, ids)
        except BadAnswer as e:
            run.error = str(e)
            errors.append(f"run {n}: {e}")
            answers.append(None)
        else:
            run.verdict, run.summary = a.verdict, a.summary
            run.findings = [{"id": f.id, "explained": f.explained, "why": f.why} for f in a.findings]
            answers.append(a)
        runs.append(run)

    verdict, reasons = combine(bundle, answers, errors, cap)
    return Decision(verdict, stage="model", ceiling=cap, reasons=cap_reasons + reasons,
                    summary=pick_summary(verdict, runs), runs=runs, **base)


def pick_summary(verdict: str, runs: list[Run]) -> str:
    """A run that agrees with the final verdict speaks for it. If none does, say whose words they are."""
    same = next((r for r in runs if r.verdict == verdict and r.summary), None)
    if same:
        return same.summary
    other = next((r for r in runs if r.summary), None)
    return f"The model said {other.verdict}: {other.summary}" if other else ""
