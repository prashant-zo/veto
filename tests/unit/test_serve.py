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
