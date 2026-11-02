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
    model_base_url: str = "https://inference.baseten.co/v1"
    model_name: str = "meta-models/muse-spark-open-1026"
    model_api_key: str | None = None
    fallback_base_url: str | None = None
    fallback_name: str | None = None
    fallback_api_key: str | None = None
    model_timeout: float = 60.0


def load() -> Settings:
    return Settings(
        prom_url=os.environ.get("VETO_PROM_URL", "http://localhost:19090"),
        loki_url=os.environ.get("VETO_LOKI_URL", "http://localhost:13100"),
        github_repo=os.environ.get("VETO_GITHUB_REPO", "prashant-zo/veto-demo-shop"),
        github_token=os.environ.get("VETO_GITHUB_TOKEN") or None,
        kube_context=os.environ.get("VETO_KUBE_CONTEXT") or None,
        http_timeout=float(os.environ.get("VETO_HTTP_TIMEOUT", "10")),
        model_base_url=os.environ.get("VETO_MODEL_BASE_URL", "https://inference.baseten.co/v1"),
        model_name=os.environ.get("VETO_MODEL_NAME", "meta-models/muse-spark-open-1026"),
        model_api_key=os.environ.get("VETO_MODEL_API_KEY") or None,
        fallback_base_url=os.environ.get("VETO_FALLBACK_BASE_URL") or None,
        fallback_name=os.environ.get("VETO_FALLBACK_NAME") or None,
        fallback_api_key=os.environ.get("VETO_FALLBACK_API_KEY") or None,
        model_timeout=float(os.environ.get("VETO_MODEL_TIMEOUT", "60")),
    )
