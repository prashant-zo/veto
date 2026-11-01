"""Gather every deterministic fact about one canary: metrics, call edges and logs."""

from dataclasses import dataclass

from .collect.kube import Kube
from .collect.loki import Loki
from .collect.prometheus import Prometheus
from .collect.query import check_hash, check_name, check_window
from .compact.logs import LogStats, collect_logs, compare_logs
from .compact.metrics import collect_side, compare, window_seconds
from .compact.model import Evidence, SideStats
from .config import Settings


@dataclass
class Gathered:
    namespace: str
    service: str
    window: str
    stable: SideStats
    canary: SideStats
    logs: LogStats
    found: list[Evidence]
    enough: bool


def gather(s: Settings, namespace: str, service: str, window: str) -> Gathered | None:
    """None when no canary is running. Raises KubeError, PromError or LokiError."""
    ns, svc, window = check_name(namespace), check_name(service), check_window(window)
    ws = window_seconds(window)
    kube = Kube(s.kube_context)
    hashes = kube.rollout_hashes(ns, svc)
    if not hashes.canary:
        return None
    stable_hash, canary_hash = check_hash(hashes.stable), check_hash(hashes.canary)

    prom = Prometheus(s.prom_url, s.http_timeout)
    stable = collect_side(prom, svc, stable_hash, window)
    canary = collect_side(prom, svc, canary_hash, window)
    found, enough = compare(svc, stable, canary, ws)

    logs = collect_logs(Loki(s.loki_url, s.http_timeout), svc, ws,
                        (stable_hash, kube.started_at(ns, stable_hash)),
                        (canary_hash, kube.started_at(ns, canary_hash)))
    found += compare_logs(svc, logs, stable.rps * ws, canary.rps * ws)
    return Gathered(ns, svc, window, stable, canary, logs, found, enough)
