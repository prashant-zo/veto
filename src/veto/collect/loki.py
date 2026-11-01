"""Read-only Loki client for log lines."""

import time
from dataclasses import dataclass

import httpx


class LokiError(RuntimeError):
    pass


@dataclass(frozen=True)
class LogLine:
    ts_ns: int
    line: str
    labels: dict[str, str]


class Loki:
    def __init__(self, base_url: str, timeout: float = 10.0, transport: httpx.BaseTransport | None = None):
        self._http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def lines(self, logql: str, since_s: int = 300, limit: int = 5000, end_ns: int | None = None) -> list[LogLine]:
        end = end_ns or time.time_ns()
        start = end - since_s * 1_000_000_000
        params = {"query": logql, "start": str(start), "end": str(end), "limit": str(limit), "direction": "backward"}
        try:
            r = self._http.get("/loki/api/v1/query_range", params=params)
            r.raise_for_status()
            body = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise LokiError(f"query failed: {e}") from e
        if body.get("status") != "success":
            raise LokiError(body.get("error", "query failed"))
        data = body["data"]
        if data.get("resultType") != "streams":
            raise LokiError(f"expected streams, got {data.get('resultType')}")
        out = []
        for stream in data["result"]:
            labels = stream.get("stream", {})
            for value in stream.get("values", []):
                out.append(LogLine(ts_ns=int(value[0]), line=value[1], labels=labels))
        out.sort(key=lambda x: x.ts_ns)
        return out
