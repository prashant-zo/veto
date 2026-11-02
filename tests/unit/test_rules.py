import json
from pathlib import Path

from veto.judge.parse import Answer, Finding
from veto.policy.rules import Rules, ceiling, code_backed, combine, floor

CASES = Path(__file__).parents[2] / "eval" / "cases"


def case(name):
    return json.loads((CASES / f"{name}.json").read_text())


def answer(verdict, explained):
    return Answer(verdict, tuple(Finding(i, ok, "") for i, ok in explained.items()), "")


def test_floor_aborts_loud_failures_and_attacks():
    assert len(floor(case("pr-4"), Rules())) == 1           # 100 percent errors
    assert len(floor(case("pr-5"), Rules())) == 3           # attack in a log line, the body and the diff
    for name in ["control", "pr-1", "pr-2", "pr-3"]:
        assert floor(case(name), Rules()) == []


def test_ceiling():
    assert ceiling(case("pr-3")) == ("promote", [])
    assert ceiling(case("pr-1"))[0] == "hold"
    assert ceiling(case("control"))[0] == "hold"


def test_soft_log_items_must_be_in_the_diff():
    pr3 = case("pr-3")
    assert all(code_backed(e, pr3["intent"]) for e in pr3["evidence"])
    pr2 = case("pr-2")   # the payments call line vanished, but no diff line logs it
    assert not code_backed(pr2["evidence"][1], pr2["intent"])


def test_combine():
    pr3 = case("pr-3")
    both = {"L1": True, "L2": True}
    assert combine(pr3, [answer("promote", both)] * 3, [], "promote") == ("promote", [])
    assert combine(pr3, [answer("promote", {"L1": True})] * 3, [], "promote")[0] == "hold"
    assert combine(pr3, [answer("promote", both), answer("hold", both), answer("promote", both)], [],
                   "promote")[0] == "hold"
    assert combine(pr3, [None] * 3, ["run 1: bad json"], "promote")[0] == "hold"
    assert combine(pr3, [answer("abort", both)] * 3, [], "promote")[0] == "hold"   # abort with nothing unexplained
    pr1 = case("pr-1")
    assert combine(pr1, [answer("promote", {"M1": True, "L1": True})] * 3, [], "hold")[0] == "hold"
    pr2 = case("pr-2")
    assert combine(pr2, [answer("abort", {"M1": False, "L1": False})] * 3, [], "hold")[0] == "abort"
