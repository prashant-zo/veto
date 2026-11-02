"""The model can make a verdict stricter, never looser.

A fake model that always says promote, a fake that answers at random, and a
fake that returns junk run over every saved case. None of them can get a
promote past the ceiling.
"""

import json
import random
from pathlib import Path

import pytest

from veto.decide import decide
from veto.judge.model import Reply
from veto.policy.rules import ceiling

CASES = sorted((Path(__file__).parents[2] / "eval" / "cases").glob("*.json"))
EXPECTED_WITH_A_YES_MODEL = {"control": "hold", "pr-1": "hold", "pr-2": "hold", "pr-3": "promote",
                             "pr-4": "abort", "pr-5": "abort", "pr-6": "promote",
                             # captured again after the blind fix: the payment call shift is hard evidence now.
                             # on the frozen bundle this was promote, only the model stood in the way
                             "pr-7": "hold"}


def reply(content):
    return Reply("fake", "fake", content, None, 0.0)


def yes_model(bundle):
    findings = [{"id": e["id"], "explained_by_pr": True, "why": "fine"} for e in bundle["evidence"]]
    text = json.dumps({"verdict": "promote", "findings": findings, "summary": "ship it"})
    return lambda _msgs: reply(text)


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_a_model_that_always_says_promote(path):
    bundle = json.loads(path.read_text())
    d = decide(bundle, yes_model(bundle))
    assert d.verdict == EXPECTED_WITH_A_YES_MODEL[path.stem]


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_random_and_broken_models_never_pass_the_ceiling(path):
    bundle = json.loads(path.read_text())
    cap = ceiling(bundle)[0]
    ids = [e["id"] for e in bundle["evidence"]] + ["X1"]
    rng = random.Random(path.stem)
    junk = [None, "", "promote", "{", '{"verdict": "promote"}', '{"verdict": "PROMOTE", "findings": "all good"}']
    for _ in range(300):
        if rng.random() < 0.3:
            text = rng.choice(junk)
        else:
            findings = [{"id": i, "explained_by_pr": rng.random() < 0.8} for i in ids if rng.random() < 0.9]
            text = json.dumps({"verdict": rng.choice(["promote", "hold", "abort", "ship"]), "findings": findings})
        d = decide(bundle, lambda _msgs, t=text: reply(t))
        if d.verdict == "promote":
            assert cap == "promote" and d.stage == "model"


def test_a_changed_bundle_is_refused():
    bundle = json.loads(CASES[0].read_text())
    bundle["evidence"] = []
    with pytest.raises(ValueError):
        decide(bundle, lambda _msgs: reply("{}"))
