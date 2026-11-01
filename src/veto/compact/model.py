"""Evidence types shared by the compactor, the bundle and the policy."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EdgeStat:
    rps: float
    err_rps: float


@dataclass(frozen=True)
class SideStats:
    hash: str
    rps: float
    err_ratio: float
    p99_ms: float | None
    edges: dict[str, EdgeStat]


@dataclass(frozen=True)
class Evidence:
    kind: str
    hard: bool
    summary: str
    stable: float | None = None
    canary: float | None = None
    detail: dict = field(default_factory=dict)
