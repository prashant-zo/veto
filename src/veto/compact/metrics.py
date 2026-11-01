"""Metric deltas and call edges, canary vs stable, from span metrics in Prometheus."""

from dataclasses import dataclass

from ..collect.prometheus import Prometheus
from ..collect.query import selector
from .model import EdgeStat, Evidence, SideStats

CALLS = "traces_span_metrics_calls_total"
DURATION_BUCKET = "traces_span_metrics_duration_milliseconds_bucket"
SERVER = "SPAN_KIND_SERVER"
CLIENT = "SPAN_KIND_CLIENT"
ERROR = "STATUS_CODE_ERROR"


@dataclass(frozen=True)
class Thresholds:
    min_requests: int = 50            # fewer requests than this on either side, we do not judge
    error_ratio_jump: float = 0.02    # canary error ratio minus stable
    latency_factor: float = 1.5       # canary p99 over stable p99
    latency_min_ms: float = 50.0      # and at least this many ms slower
    edge_min_per_req: float = 0.2     # an edge needs this many calls per request to count
    edge_gone_factor: float = 0.05    # canary under 5 percent of stable means the edge is gone
    edge_shift_factor: float = 0.5    # more than 50 percent up or down is a shift
    edge_error_jump: float = 0.05     # canary edge error ratio minus stable


def window_seconds(window: str) -> int:
    return int(window[:-1]) * {"s": 1, "m": 60, "h": 3600}[window[-1]]


def _one(prom: Prometheus, promql: str) -> float:
    res = prom.query(promql)
    return res[0].value if res else 0.0


def _ratio(part: float, whole: float) -> float:
    return part / whole if whole > 0 else 0.0


def collect_side(prom: Prometheus, service: str, pod_hash: str, window: str) -> SideStats:
    base = {"service_name": service, "rollouts_pod_template_hash": pod_hash}
    srv = selector(**base, span_kind=SERVER)
    srv_err = selector(**base, span_kind=SERVER, status_code=ERROR)
    cli = selector(**base, span_kind=CLIENT)
    cli_err = selector(**base, span_kind=CLIENT, status_code=ERROR)

    rps = _one(prom, f"sum(rate({CALLS}{srv}[{window}]))")
    err = _one(prom, f"sum(rate({CALLS}{srv_err}[{window}]))")
    p99 = prom.query(f"histogram_quantile(0.99, sum by (le) (rate({DURATION_BUCKET}{srv}[{window}])))")
    calls = prom.query(f"sum by (server_address) (rate({CALLS}{cli}[{window}]))")
    errs = prom.query(f"sum by (server_address) (rate({CALLS}{cli_err}[{window}]))")

    err_by_dest = {s.labels.get("server_address", ""): s.value for s in errs}
    edges = {
        s.labels["server_address"]: EdgeStat(rps=s.value, err_rps=err_by_dest.get(s.labels["server_address"], 0.0))
        for s in calls if s.labels.get("server_address")
    }
    return SideStats(hash=pod_hash, rps=rps, err_ratio=_ratio(err, rps),
                     p99_ms=p99[0].value if p99 else None, edges=edges)


def compare(service: str, stable: SideStats, canary: SideStats, window_s: int,
            t: Thresholds | None = None) -> tuple[list[Evidence], bool]:
    """Deterministic evidence, plus whether both sides had enough traffic to judge."""
    t = t or Thresholds()
    enough = min(stable.rps, canary.rps) * window_s >= t.min_requests
    found: list[Evidence] = []

    if canary.err_ratio - stable.err_ratio > t.error_ratio_jump:
        found.append(Evidence("error_rate_up", True,
                              f"{service} error ratio {stable.err_ratio:.1%} on stable, {canary.err_ratio:.1%} on canary",
                              stable.err_ratio, canary.err_ratio))

    if stable.p99_ms is not None and canary.p99_ms is not None:
        if canary.p99_ms > stable.p99_ms * t.latency_factor and canary.p99_ms - stable.p99_ms > t.latency_min_ms:
            found.append(Evidence("latency_up", True,
                                  f"{service} p99 {stable.p99_ms:.0f}ms on stable, {canary.p99_ms:.0f}ms on canary",
                                  stable.p99_ms, canary.p99_ms))

    empty = EdgeStat(0.0, 0.0)
    for dest in sorted(set(stable.edges) | set(canary.edges)):
        s, c = stable.edges.get(dest, empty), canary.edges.get(dest, empty)
        s_per, c_per = _ratio(s.rps, stable.rps), _ratio(c.rps, canary.rps)
        detail = {"destination": dest}
        text = f"{service} calls {dest} {s_per:.2f} times per request on stable, {c_per:.2f} on canary"
        if s_per >= t.edge_min_per_req and c_per < s_per * t.edge_gone_factor:
            found.append(Evidence("edge_missing", True, text, s_per, c_per, detail))
        elif c_per >= t.edge_min_per_req and s_per < c_per * t.edge_gone_factor:
            found.append(Evidence("edge_new", True, text, s_per, c_per, detail))
        elif (s_per >= t.edge_min_per_req and c_per >= t.edge_min_per_req
              and abs(c_per - s_per) / s_per > t.edge_shift_factor):
            found.append(Evidence("edge_rate_shift", True, text, s_per, c_per, detail))

        s_err, c_err = _ratio(s.err_rps, s.rps), _ratio(c.err_rps, c.rps)
        if c_err - s_err > t.edge_error_jump:
            found.append(Evidence("edge_errors", True,
                                  f"{service} calls to {dest} fail {s_err:.1%} on stable, {c_err:.1%} on canary",
                                  s_err, c_err, detail))
    return found, enough
