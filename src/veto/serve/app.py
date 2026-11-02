"""HTTP service for Argo Rollouts: one verdict per canary, worked out once.

Argo's web metric calls GET /v1/verdict during the analysis step. The first call
starts the work and waits for it, later calls for the same canary get the same
decision. Anything that breaks inside Veto answers hold, so a broken Veto pauses
a release, it never ships one.
"""

import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as Waiting

from fastapi import FastAPI, HTTPException

from .. import config
from ..bundle import collect
from ..collect.kube import Kube
from ..collect.query import BadInput, check_name
from ..decide import decide
from ..judge.model import ModelClient, endpoints
from ..notify import events

log = logging.getLogger("veto")

WINDOW = "2m"
WAIT_S = 50       # argo's web metric times out at 60s, answer before that
KEEP_S = 1800     # a decision is reused for the same canary for 30 minutes
RECENT = 20


def hold(reason: str, **extra) -> dict:
    return {"verdict": "hold", "stage": "veto", "reasons": [reason], "summary": "", **extra}


def judge_rollout(namespace: str, rollout: str) -> dict:
    """The real work: bundle, decision, event. Never raises."""
    s = config.load()
    try:
        bundle = collect(namespace, rollout, WINDOW)
        if bundle is None:
            out = hold("no canary running")
        else:
            d = decide(bundle, ModelClient(endpoints(s), s.model_timeout).ask)
            out = {"verdict": d.verdict, "stage": d.stage, "canary_tag": d.canary_tag, "bundle_hash": d.bundle_hash,
                   "ceiling": d.ceiling, "reasons": d.reasons, "summary": d.summary,
                   "runs": [{"model": r.model, "seconds": r.seconds, "verdict": r.verdict, "error": r.error}
                            for r in d.runs]}
    except Exception as e:  # fail closed: any error is a hold
        log.exception("decision failed")
        out = hold(f"veto error: {type(e).__name__}")
    try:
        events.post(s.kube_context, namespace, rollout, out)
    except Exception as e:  # noqa: BLE001  an event is nice to have, the verdict still goes back to argo
        log.warning("event not written: %s", type(e).__name__)
    return out


def canary_hash(namespace: str, rollout: str) -> str | None:
    return Kube(config.load().kube_context).rollout_hashes(namespace, rollout).canary


class Verdicts:
    def __init__(self, work: Callable[[str, str], dict], lookup: Callable[[str, str], str | None],
                 wait_s: float = WAIT_S, keep_s: float = KEEP_S):
        self._work, self._lookup = work, lookup
        self._wait_s, self._keep_s = wait_s, keep_s
        self._pool = ThreadPoolExecutor(4)
        self._lock = threading.Lock()
        self._jobs: dict[tuple, tuple[float, Future]] = {}
        self.recent: deque = deque(maxlen=RECENT)

    def _done(self, key: tuple, fut: Future) -> None:
        out = {"namespace": key[0], "rollout": key[1], "canary_hash": key[2], **fut.result()}
        self.recent.appendleft(out)
        log.info(json.dumps({"event": "decision", **{k: out.get(k) for k in
                             ("namespace", "rollout", "canary_tag", "verdict", "stage", "bundle_hash")}}))

    def get(self, namespace: str, rollout: str) -> dict:
        try:
            h = self._lookup(namespace, rollout)
        except Exception as e:  # noqa: BLE001
            return hold(f"could not read the rollout: {type(e).__name__}")
        if not h:
            return hold("no canary running")
        key = (namespace, rollout, h)
        now = time.monotonic()
        with self._lock:
            for k in [k for k, (t, _) in self._jobs.items() if now - t > self._keep_s]:
                del self._jobs[k]
            if key not in self._jobs:
                fut = self._pool.submit(self._work, namespace, rollout)
                fut.add_done_callback(lambda f, k=key: self._done(k, f))
                self._jobs[key] = (now, fut)
            fut = self._jobs[key][1]
        try:
            return fut.result(timeout=self._wait_s)
        except Waiting:
            return {"verdict": "pending", "stage": "veto", "reasons": ["still working, argo will pause the rollout"],
                    "summary": ""}


def create_app(verdicts: Verdicts | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    v = verdicts or Verdicts(judge_rollout, canary_hash)
    app = FastAPI(title="veto", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.get("/v1/verdict")
    def verdict(namespace: str, rollout: str) -> dict:
        try:
            ns, ro = check_name(namespace), check_name(rollout)
        except BadInput as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return v.get(ns, ro)

    @app.get("/v1/decisions")
    def decisions() -> list[dict]:
        return list(v.recent)

    return app


app = create_app()
