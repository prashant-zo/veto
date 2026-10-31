"""Smoke test for the judge model.

Checks auth and model name, where the reasoning text lands, whether json mode
is accepted, and whether the verdict is stable on a small silent bug bundle.

usage: make smoke  (reads VETO_MODEL_* from .env)
"""

import json
import os
import re
import sys
import time
from collections import Counter

from openai import OpenAI

BASE_URL = os.environ.get("VETO_MODEL_BASE_URL", "https://inference.baseten.co/v1")
MODEL = os.environ.get("VETO_MODEL_NAME", "meta-models/muse-spark-open-1026")
KEY = os.environ.get("VETO_MODEL_API_KEY")
RUNS = 5

if not KEY:
    sys.exit("VETO_MODEL_API_KEY is not set, check .env")

client = OpenAI(base_url=BASE_URL, api_key=KEY)

# silent bug: error rate barely moves, but canary stopped calling payments
BUNDLE = {
    "canary_only_log_templates": [
        {"id": "L1", "template": "payment client: connection refused to payments:<*>",
         "canary_count": 42, "stable_count": 0},
    ],
    "metric_deltas": [
        {"id": "M1", "name": "http_error_rate", "stable": 0.002, "canary": 0.003},
        {"id": "M2", "name": "p99_latency_ms", "stable": 180, "canary": 175},
    ],
    "call_edge_changes": [
        {"id": "E1", "edge": "checkout -> payments", "stable_calls": 980, "canary_calls": 0},
    ],
}
VALID_IDS = {"L1", "M1", "M2", "E1"}
VALID_VERDICTS = {"promote", "hold", "abort"}

SYSTEM = (
    "You judge a Kubernetes canary release by comparing canary vs stable evidence. "
    "Reply with only a JSON object and nothing else: "
    '{"verdict": "promote" | "hold" | "abort", '
    '"evidence_ids": [ids from the bundle that support the verdict], '
    '"reason": "one sentence"}. '
    "Only cite ids that appear in the bundle. If evidence is missing or unclear, use hold."
)


def reasoning_of(msg):
    return getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)


def extract_json(text):
    if text is None:
        return None
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def call(messages, **extra):
    t0 = time.time()
    resp = client.chat.completions.create(model=MODEL, messages=messages, **extra)
    return resp, time.time() - t0


# 1. basic call
resp, dt = call([{"role": "user", "content": "Reply with the single word: ok"}])
msg = resp.choices[0].message
print(f"[1] basic call  latency={dt:.2f}s  content={msg.content!r}")
print(f"    usage: {resp.usage}")
print(f"    extra fields on message: {sorted((msg.model_extra or {}).keys())}")
r = reasoning_of(msg)
print(f"    reasoning in separate field: {r is not None}" + (f" ({len(r)} chars)" if r else ""))
print(f"    reasoning inline in content: {'</think>' in (msg.content or '')}")

# 2. is json mode accepted
messages = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": json.dumps(BUNDLE)},
]
json_mode = {"response_format": {"type": "json_object"}}
try:
    resp, _ = call(messages, temperature=0, **json_mode)
    print("[2] response_format json_object: accepted")
    print(f"    raw content: {(resp.choices[0].message.content or '')[:300]!r}")
except Exception as e:  # noqa: BLE001
    print(f"[2] response_format json_object: rejected ({type(e).__name__}: {e})")
    json_mode = {}

# 3. verdict stability
verdicts, latencies, failures = Counter(), [], []
for i in range(RUNS):
    try:
        resp, dt = call(messages, temperature=0, **json_mode)
    except Exception as e:  # noqa: BLE001
        failures.append(f"run {i + 1}: api error {type(e).__name__}")
        continue
    latencies.append(dt)
    out = extract_json(resp.choices[0].message.content)
    if not out:
        failures.append(f"run {i + 1}: not valid json")
        continue
    v = out.get("verdict")
    ids = set(out.get("evidence_ids") or [])
    if v not in VALID_VERDICTS:
        failures.append(f"run {i + 1}: bad verdict {v!r}")
    elif not ids or not ids <= VALID_IDS:
        failures.append(f"run {i + 1}: bad evidence_ids {sorted(ids)}")
    verdicts[v] += 1
    print(f"[3] run {i + 1}: verdict={v} ids={sorted(ids)} latency={dt:.2f}s reason={out.get('reason')!r}")

print("\n=== summary ===")
print(f"verdicts: {dict(verdicts)}  (expected: abort every time)")
if latencies:
    print(f"mean latency: {sum(latencies) / len(latencies):.2f}s  max: {max(latencies):.2f}s")
print(f"failures: {len(failures)}/{RUNS}")
for f in failures:
    print(f"  - {f}")
