"""Talk to the judge model over the OpenAI chat API, with a fallback endpoint.

Only Muse models are configured: Muse Spark Open on Baseten first,
Muse Spark 1.3 on the Meta API when Baseten fails.
"""

import time
from dataclasses import dataclass

import httpx
from openai import OpenAI

from ..config import Settings


@dataclass(frozen=True)
class Endpoint:
    label: str
    base_url: str
    model: str
    api_key: str


@dataclass(frozen=True)
class Reply:
    label: str
    model: str
    content: str | None
    reasoning: str | None
    seconds: float
    error: str | None = None


def endpoints(s: Settings, only: str | None = None) -> list[Endpoint]:
    out = []
    if s.model_api_key:
        out.append(Endpoint("primary", s.model_base_url, s.model_name, s.model_api_key))
    if s.fallback_base_url and s.fallback_name and s.fallback_api_key:
        out.append(Endpoint("fallback", s.fallback_base_url, s.fallback_name, s.fallback_api_key))
    return [e for e in out if only is None or e.label == only]


class ModelClient:
    def __init__(self, eps: list[Endpoint], timeout: float = 60.0, transport: httpx.BaseTransport | None = None):
        http = httpx.Client(transport=transport, timeout=timeout) if transport else None
        self._eps = [(ep, OpenAI(base_url=ep.base_url, api_key=ep.api_key, timeout=timeout, max_retries=1,
                                 http_client=http)) for ep in eps]

    def ask(self, messages: list[dict]) -> Reply:
        """First endpoint that answers wins. Errors keep only the type name, never request details."""
        errors = []
        for ep, client in self._eps:
            start = time.monotonic()
            try:
                resp = client.chat.completions.create(model=ep.model, messages=messages, temperature=0,
                                                      response_format={"type": "json_object"})
            except Exception as e:  # noqa: BLE001  any api failure moves on to the next endpoint
                errors.append(f"{ep.label} {type(e).__name__}")
                continue
            msg = resp.choices[0].message
            reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
            return Reply(ep.label, ep.model, msg.content, reasoning, round(time.monotonic() - start, 2))
        return Reply("none", "", None, None, 0.0, ", ".join(errors) or "no model endpoint configured")
