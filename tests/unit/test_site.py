import json
import shutil
from pathlib import Path

from veto.decide import decide
from veto.judge.model import Reply
from veto.site import build

EVAL = Path(__file__).parents[2] / "eval"


def hold(msgs):
    ids = [ln.split('"')[3] for ln in msgs[1]["content"].splitlines() if '"id":' in ln]
    text = json.dumps({"verdict": "hold", "findings": [{"id": i, "explained_by_pr": True, "why": "w"} for i in ids]})
    return Reply("fake", "fake-model", text, "x" * 5000, 1.0)


def repo(tmp_path):
    shutil.copytree(EVAL / "cases", tmp_path / "eval" / "cases")
    shutil.copytree(EVAL / "results", tmp_path / "eval" / "results")
    shutil.copy(EVAL / "labels.json", tmp_path / "eval" / "labels.json")
    runs = tmp_path / "eval" / "runs"
    runs.mkdir()
    for p in sorted((tmp_path / "eval" / "cases").glob("*.json")):
        d = decide(json.loads(p.read_text()), hold)
        (runs / p.name).write_text(json.dumps(d.to_dict()))
    return tmp_path


def test_site_data(tmp_path):
    data = build(repo(tmp_path))
    cases = {c["case"]: c for c in data["cases"]}
    assert set(cases) == {"control", "pr-1", "pr-2", "pr-3", "pr-4", "pr-5", "pr-6", "pr-7"}
    assert cases["pr-2"]["decision"]["verdict"] == "hold" and cases["pr-2"]["baseline"] == "promote"
    assert cases["pr-5"]["decision"]["stage"] == "floor" and cases["control"]["pr"] is None
    assert len(cases["pr-3"]["decision"]["runs"][0]["reasoning"]) == 1200
    assert data["eval"]["primary"]["veto"]["scored"] > 0 and data["attacks"]["count"] == 80


def test_a_decision_on_another_bundle_is_left_out(tmp_path):
    root = repo(tmp_path)
    run = root / "eval" / "runs" / "pr-3.json"
    d = json.loads(run.read_text())
    d["bundle_hash"] = "sha256:other"
    run.write_text(json.dumps(d))
    assert next(c for c in build(root)["cases"] if c["case"] == "pr-3")["decision"] is None
