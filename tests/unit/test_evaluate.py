import json
from pathlib import Path

from veto.decide import Run, pick_summary
from veto.evaluate import baseline, grade, report, run, score
from veto.judge.model import Reply

ROOT = Path(__file__).parents[2] / "eval"


def test_baseline_only_sees_errors_and_latency():
    got = {p.stem: baseline(json.loads(p.read_text())) for p in sorted((ROOT / "cases").glob("*.json"))}
    assert got == {"control": "promote", "pr-1": "promote", "pr-2": "promote", "pr-3": "promote",
                   "pr-4": "abort", "pr-5": "promote", "pr-6": "promote", "pr-7": "promote"}


def test_grade():
    assert grade("hold", "hold") == "right"
    assert grade("hold", "promote") == "looser"
    assert grade("promote", "abort") == "stricter"
    assert grade(None, "abort") == "held out"


def test_eval_with_a_model_that_always_says_hold():
    def hold(msgs):
        ids = [ln.split('"')[3] for ln in msgs[1]["content"].splitlines() if '"id":' in ln]
        text = json.dumps({"verdict": "hold", "findings": [{"id": i, "explained_by_pr": True} for i in ids]})
        return Reply("fake", "fake", text, None, 1.5)

    labels = json.loads((ROOT / "labels.json").read_text())
    rows = run(ROOT / "cases", labels, hold)
    assert {r.case: r.veto[0] for r in rows} == {"control": "hold", "pr-1": "hold", "pr-2": "hold",
                                                  "pr-3": "hold", "pr-4": "abort", "pr-5": "abort",
                                                  "pr-6": "hold", "pr-7": "hold"}
    assert score(rows, "veto") == {"right": 4, "stricter": 2, "looser": 2, "shipped": 0, "scored": 8}
    assert score(rows, "baseline") == {"right": 3, "stricter": 0, "looser": 5, "shipped": 5, "scored": 8}
    assert "| pr-2 | abort | hold (looser) | model | promote (looser) | 1.5s |" in report(rows, "fake")


def test_summary_comes_from_a_run_that_agrees():
    runs = [Run("p", "m", 1.0, "promote", summary="safe to promote"), Run("p", "m", 1.0, "hold", summary="look first")]
    assert pick_summary("hold", runs) == "look first"
    assert pick_summary("abort", runs) == "The model said promote: safe to promote"
    assert pick_summary("hold", []) == ""


def test_rescore_keeps_the_verdicts_and_adds_late_labels(tmp_path):
    from veto.evaluate import Row, rescore
    saved = tmp_path / "r.json"
    rows = [Row("pr-7", None, ["hold", "hold"], "model", "promote", 7.0)]
    saved.write_text(json.dumps([r.__dict__ for r in rows]))
    got = rescore(saved, {"pr-7": {"expected": "abort"}})
    assert got[0].veto == ["hold", "hold"] and got[0].expected == "abort"
    assert score(got, "veto") == {"right": 0, "stricter": 0, "looser": 2, "shipped": 0, "scored": 2}
