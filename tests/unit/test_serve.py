import threading

from fastapi.testclient import TestClient

from veto.serve.app import Verdicts, create_app


def client(work, lookup=lambda ns, ro: "abc123", wait_s=2.0):
    v = Verdicts(work, lookup, wait_s=wait_s)
    return TestClient(create_app(v)), v


def test_one_decision_per_canary():
    calls = []

    def work(ns, ro):
        calls.append((ns, ro))
        return {"verdict": "promote", "stage": "model", "canary_tag": "pr-3-4a152ce", "reasons": [], "summary": "ok"}

    c, _ = client(work)
    for _ in range(3):
        r = c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"})
        assert r.status_code == 200 and r.json()["verdict"] == "promote"
    assert calls == [("shop", "checkout")]
    assert c.get("/v1/decisions").json()[0]["canary_hash"] == "abc123"


def test_new_canary_gets_a_new_decision():
    hashes = iter(["aaa", "bbb"])
    calls = []
    c, _ = client(lambda ns, ro: calls.append(1) or {"verdict": "hold"}, lookup=lambda ns, ro: next(hashes))
    c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"})
    c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"})
    assert len(calls) == 2


def test_no_canary_or_broken_lookup_is_hold():
    c, _ = client(lambda ns, ro: {"verdict": "promote"}, lookup=lambda ns, ro: None)
    assert c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"}).json()["verdict"] == "hold"

    def broken(ns, ro):
        raise RuntimeError("api down")
    c, _ = client(lambda ns, ro: {"verdict": "promote"}, lookup=broken)
    assert c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"}).json()["verdict"] == "hold"


def test_slow_work_answers_pending_then_the_verdict():
    gate = threading.Event()

    def work(ns, ro):
        gate.wait(5)
        return {"verdict": "abort"}

    c, _ = client(work, wait_s=0.1)
    assert c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"}).json()["verdict"] == "pending"
    gate.set()
    c2 = c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"})
    assert c2.json()["verdict"] == "abort"


def test_bad_names_are_rejected():
    c, _ = client(lambda ns, ro: {"verdict": "promote"})
    assert c.get("/v1/verdict", params={"namespace": "shop", "rollout": 'x"} or 1'}).status_code == 400
    assert c.get("/healthz").json() == {"ok": True}


# the veto ui: the page, its live data, and what stays out of argo's answer

import base64
import hashlib
import json
import re
from pathlib import Path

from veto.decide import decide
from veto.judge.model import Reply
from veto.serve.app import STATIC

CASES = Path(__file__).parents[2] / "eval" / "cases"


def all_held(msgs):
    ids = [ln.split('"')[3] for ln in msgs[1]["content"].splitlines() if '"id":' in ln]
    text = json.dumps({"verdict": "hold", "findings": [{"id": i, "explained_by_pr": True, "why": "w"} for i in ids]})
    return Reply("fake", "fake-model", text, "thinking", 1.0)


def judged(case):
    b = json.loads((CASES / f"{case}.json").read_text())
    d = decide(b, all_held)
    return {"verdict": d.verdict, "stage": d.stage, "canary_tag": d.canary_tag, "bundle_hash": d.bundle_hash,
            "ceiling": d.ceiling, "reasons": d.reasons, "summary": d.summary, "runs": [],
            "_detail": {"bundle": b, "decision": d.to_dict()}}


def test_the_bundle_never_goes_back_to_argo():
    c, _ = client(lambda ns, ro: judged("pr-2"))
    r = c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"}).json()
    assert r["verdict"] == "hold" and "_detail" not in r
    assert "_detail" not in c.get("/v1/decisions").json()[0]


def test_ui_data_shows_each_decision_oldest_first():
    work = {"checkout": lambda: judged("pr-2"), "pricing": lambda: {"verdict": "hold", "stage": "veto",
                                                                     "reasons": ["veto error: Boom"], "summary": ""}}
    c, _ = client(lambda ns, ro: work[ro]())
    assert c.get("/data.json").json()["cases"] == []
    c.get("/v1/verdict", params={"namespace": "shop", "rollout": "checkout"})
    c.get("/v1/verdict", params={"namespace": "shop", "rollout": "pricing"})
    data = c.get("/data.json").json()
    assert data["mode"] == "live" and data["eval"] is None and data["attacks"] is None
    first, second = data["cases"]
    assert first["label"] == "pr-2" and first["pr"]["number"] == 2 and first["rollout"] == "checkout"
    assert first["decision"]["verdict"] == "hold" and first["evidence"] and first["baseline"] == "promote"
    assert first["decision"]["runs"][0]["reasoning"] == "thinking"
    assert second["stable"] is None and second["decision"]["reasons"] == ["veto error: Boom"]
    assert first["case"] != second["case"]


def test_ui_page_only_runs_its_own_script():
    c, _ = client(lambda ns, ro: {"verdict": "hold"})
    r = c.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    script = re.search(r"<script>(.*?)</script>", r.text, re.DOTALL).group(1)
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = r.headers["content-security-policy"]
    assert f"script-src 'sha256-{digest}';" in csp and "unsafe-eval" not in csp and "frame-ancestors 'none'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert c.get("/icon.svg").headers["content-type"] == "image/svg+xml"
    assert (STATIC / "index.html").read_text().count("<script") == 1


def test_ui_can_be_turned_off():
    v = Verdicts(lambda ns, ro: {"verdict": "hold"}, lambda ns, ro: "abc123", wait_s=2.0)
    c = TestClient(create_app(v, ui=False))
    assert c.get("/").status_code == 404 and c.get("/data.json").status_code == 404
    assert c.get("/healthz").json() == {"ok": True}
