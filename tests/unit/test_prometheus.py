import httpx
import pytest

from veto.collect.prometheus import PromError, Prometheus


def make(handler):
    return Prometheus("http://prom", transport=httpx.MockTransport(handler))


def test_query_returns_samples_and_skips_nan():
    def handler(request):
        assert request.url.path == "/api/v1/query"
        assert request.url.params["query"] == "up"
        return httpx.Response(200, json={"status": "success", "data": {"resultType": "vector", "result": [
            {"metric": {"job": "a"}, "value": [1, "2.5"]},
            {"metric": {"job": "b"}, "value": [1, "NaN"]},
        ]}})

    out = make(handler).query("up")
    assert len(out) == 1
    assert out[0].labels == {"job": "a"}
    assert out[0].value == 2.5


def test_bad_query_raises():
    with pytest.raises(PromError):
        make(lambda r: httpx.Response(400, json={"status": "error", "error": "parse error"})).query("sum(")


def test_non_vector_raises():
    def handler(request):
        return httpx.Response(200, json={"status": "success", "data": {"resultType": "matrix", "result": []}})

    with pytest.raises(PromError):
        make(handler).query("up[1m]")
