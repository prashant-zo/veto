"""Read-only Prometheus client. Instant queries only."""

from dataclasses import dataclass

import httpx


class PromError(RuntimeError):
    pass


@dataclass(frozen=True)
class Sample:
    labels: dict[str, str]
    value: float


class Prometheus:
    def __init__(self, base_url: str, timeout: float = 10.0, transport: httpx.BaseTransport | None = None):
        self._http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def query(self, promql: str) -> list[Sample]:
        try:
            r = self._http.get("/api/v1/query", params={"query": promql})
            r.raise_for_status()
            body = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise PromError(f"query failed: {e}") from e
        if body.get("status") != "success":
            raise PromError(body.get("error", "query failed"))
        data = body["data"]
        if data.get("resultType") != "vector":
            raise PromError(f"expected vector, got {data.get('resultType')}")
        out = []
        for item in data["result"]:
            value = float(item["value"][1])
            if value != value:  # NaN, e.g. a quantile with no data
                continue
            out.append(Sample(labels=item["metric"], value=value))
        return out
