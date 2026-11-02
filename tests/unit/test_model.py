import json

import httpx

from veto.config import Settings
from veto.judge.model import Endpoint, ModelClient, endpoints

EPS = [Endpoint("primary", "https://primary.test/v1", "muse-a", "k1"),
       Endpoint("fallback", "https://fallback.test/v1", "muse-b", "k2")]


def completion(content, reasoning=None):
    msg = {"role": "assistant", "content": content}
    if reasoning:
        msg["reasoning_content"] = reasoning
    return {"id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop", "message": msg}]}


def test_falls_back_when_primary_fails():
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append((request.url.host, body["model"], body["temperature"], body["response_format"]["type"]))
        if request.url.host == "primary.test":
            return httpx.Response(503, json={"error": {"message": "down"}})
        return httpx.Response(200, json=completion('{"verdict": "hold"}', reasoning="thinking"))

    r = ModelClient(EPS, transport=httpx.MockTransport(handler)).ask([{"role": "user", "content": "hi"}])
    assert (r.label, r.model, r.content, r.reasoning, r.error) == ("fallback", "muse-b", '{"verdict": "hold"}',
                                                                    "thinking", None)
    assert seen[-1] == ("fallback.test", "muse-b", 0, "json_object")


def test_all_down_is_an_error_without_details():
    r = ModelClient(EPS, transport=httpx.MockTransport(lambda req: httpx.Response(500))).ask([])
    assert r.content is None and r.error == "primary InternalServerError, fallback InternalServerError"


def test_endpoints_from_settings():
    s = Settings("p", "l", "o/r", None, None, 5.0, model_api_key="k", fallback_base_url="https://f/v1",
                 fallback_name="muse-spark-1.3", fallback_api_key="k2")
    assert [e.label for e in endpoints(s)] == ["primary", "fallback"]
    assert [e.label for e in endpoints(s, only="fallback")] == ["fallback"]
    assert endpoints(Settings("p", "l", "o/r", None, None, 5.0)) == []
