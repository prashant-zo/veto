import httpx
import pytest

from veto.collect.loki import Loki, LokiError


def make(handler):
    return Loki("http://loki", transport=httpx.MockTransport(handler))


def test_lines_are_sorted_by_time():
    def handler(request):
        assert request.url.path == "/loki/api/v1/query_range"
        return httpx.Response(200, json={"status": "success", "data": {"resultType": "streams", "result": [
            {"stream": {"pod": "x"}, "values": [["2", "second"], ["1", "first"]]},
        ]}})

    out = make(handler).lines('{service_name="checkout"}', since_s=60, end_ns=10_000_000_000)
    assert [x.line for x in out] == ["first", "second"]
    assert out[0].labels == {"pod": "x"}


def test_error_raises():
    with pytest.raises(LokiError):
        make(lambda r: httpx.Response(500, text="boom")).lines("{a=\"b\"}")
