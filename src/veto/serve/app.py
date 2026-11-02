"""HTTP service for Argo Rollouts: one verdict per canary, worked out once.

Argo's web metric calls GET /v1/verdict during the analysis step. The first call
starts the work and waits for it, later calls for the same canary get the same
decision. Anything that breaks inside Veto answers hold, so a broken Veto pauses
a release, it never ships one.

GET / is the Veto UI: the replay page, fed with this Veto's own decisions from
GET /data.json. They are kept in memory, the last RECENT of them, so a restart
clears them. Turn it off with VETO_UI=false.
"""

import base64
import hashlib
import json
import logging
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as Waiting
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response

from .. import config
from ..bundle import collect
from ..collect.kube import Kube
from ..collect.query import BadInput, check_name
from ..decide import decide
from ..judge.model import ModelClient, endpoints
from ..notify import events
from ..view import case_view, decision_view, short_tag

log = logging.getLogger("veto")

WINDOW = "2m"
WAIT_S = 50       # argo's web metric times out at 60s, answer before that
KEEP_S = 1800     # a decision is reused for the same canary for 30 minutes
RECENT = 50       # decisions the ui and /v1/decisions remember
STATIC = Path(__file__).parent / "static"


def hold(reason: str, **extra) -> dict:
    return {"verdict": "hold", "stage": "veto", "reasons": [reason], "summary": "", **extra}


def public(out: dict) -> dict:
    """What argo, events and /v1/decisions get: everything but the _detail kept for the ui."""
    return {k: v for k, v in out.items() if not k.startswith("_")}


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
                            for r in d.runs],
                   "_detail": {"bundle": bundle, "decision": d.to_dict()}}
    except Exception as e:  # fail closed: any error is a hold
        log.exception("decision failed")
        out = hold(f"veto error: {type(e).__name__}")
    try:
        events.post(s.kube_context, namespace, rollout, public(out))
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
        self._seen = threading.Lock()   # own lock: a done callback can run inside get() while _lock is held
        self._jobs: dict[tuple, tuple[float, Future]] = {}
        self.recent: deque = deque(maxlen=RECENT)

    def _done(self, key: tuple, fut: Future) -> None:
        out = {"namespace": key[0], "rollout": key[1], "canary_hash": key[2],
               "decided_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), **fut.result()}
        with self._seen:
            self.recent.appendleft(out)
        log.info(json.dumps({"event": "decision", **{k: out.get(k) for k in
                             ("namespace", "rollout", "canary_tag", "verdict", "stage", "bundle_hash")}}))

    def decisions(self) -> list[dict]:
        """Newest first, with the _detail the ui needs."""
        with self._seen:
            return list(self.recent)

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
            return public(fut.result(timeout=self._wait_s))
        except Waiting:
            return {"verdict": "pending", "stage": "veto", "reasons": ["still working, argo will pause the rollout"],
                    "summary": ""}


def live_case(rec: dict) -> dict:
    """One remembered decision in the shape the page reads."""
    name = f"{rec['namespace']}.{rec['rollout']}.{rec['canary_hash']}"
    detail = rec.get("_detail") or {}
    if detail.get("bundle") and detail.get("decision"):
        case = case_view(name, detail["bundle"], decision_view(detail["decision"]))
    else:   # held before there was a bundle: no canary, or veto broke
        case = {"case": name, "expected": None, "why": "", "baseline": None, "canary_tag": rec.get("canary_tag"),
                "service": rec["rollout"], "window": WINDOW, "created_at": rec["decided_at"], "bundle_hash": None,
                "stable": None, "canary": None, "traffic": None, "pr": None, "evidence": [],
                "decision": {"verdict": rec.get("verdict", "hold"), "stage": rec.get("stage", "veto"), "ceiling": None,
                             "reasons": rec.get("reasons") or [], "summary": rec.get("summary") or "",
                             "bundle_hash": None, "runs": []}}
    case.update(label=short_tag(case["canary_tag"]), namespace=rec["namespace"], rollout=rec["rollout"],
                decided_at=rec["decided_at"])
    return case


def live_data(records: list[dict]) -> dict:
    return {"mode": "live", "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model": config.load().model_name, "keep": RECENT,
            "cases": [live_case(r) for r in reversed(records)],     # oldest first, like the track reads
            "eval": None, "attacks": None}


def page() -> tuple[bytes, str]:
    """The page and a content security policy that allows only its own inline script."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
                      for s in scripts)
    csp = (f"default-src 'none'; script-src {hashes}; connect-src 'self'; img-src 'self'; "
           "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
           "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
    return html.encode(), csp


SAFE = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}


def create_app(verdicts: Verdicts | None = None, ui: bool | None = None) -> FastAPI:
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
        return [public(d) for d in v.decisions()]

    if config.load().ui if ui is None else ui:
        html, csp = page()
        icon = (STATIC / "icon.svg").read_bytes()

        @app.get("/", include_in_schema=False)
        def index() -> Response:
            return Response(html, media_type="text/html; charset=utf-8",
                            headers={**SAFE, "Content-Security-Policy": csp, "X-Frame-Options": "DENY"})

        @app.get("/data.json", include_in_schema=False)
        def data() -> JSONResponse:
            return JSONResponse(live_data(v.decisions()), headers=SAFE)

        @app.get("/icon.svg", include_in_schema=False)
        def favicon() -> Response:
            return Response(icon, media_type="image/svg+xml", headers={"X-Content-Type-Options": "nosniff"})

    return app


app = create_app()
