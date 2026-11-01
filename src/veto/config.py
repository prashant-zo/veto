"""Settings from env vars. Defaults fit the local kind setup."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    prom_url: str
    loki_url: str
    github_repo: str
    github_token: str | None
    kube_context: str | None
    http_timeout: float


def load() -> Settings:
    return Settings(
        prom_url=os.environ.get("VETO_PROM_URL", "http://localhost:19090"),
        loki_url=os.environ.get("VETO_LOKI_URL", "http://localhost:13100"),
        github_repo=os.environ.get("VETO_GITHUB_REPO", "prashant-zo/veto-demo-shop"),
        github_token=os.environ.get("VETO_GITHUB_TOKEN") or None,
        kube_context=os.environ.get("VETO_KUBE_CONTEXT") or None,
        http_timeout=float(os.environ.get("VETO_HTTP_TIMEOUT", "10")),
    )
