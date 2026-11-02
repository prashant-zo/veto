"""Write each decision as a Kubernetes Event on the Rollout.

It shows up in kubectl describe rollout and in kubectl argo rollouts get,
next to the analysis run. The message always says it comes from Veto.
"""

import os
from datetime import UTC, datetime

from kubernetes import client

from ..collect.kube import load_config

REASONS = {"promote": "VetoPromote", "hold": "VetoHold", "abort": "VetoAbort"}
MAX_MESSAGE = 1000


def message(decision: dict) -> str:
    text = f"Veto {decision['verdict'].upper()} for {decision.get('canary_tag') or 'this canary'}."
    if decision.get("summary"):
        text += f" {decision['summary']}"
    reasons = decision.get("reasons") or []
    if reasons:
        text += " Why: " + "; ".join(reasons[:3])
    return text if len(text) <= MAX_MESSAGE else text[:MAX_MESSAGE - 3] + "..."


def event_body(namespace: str, rollout: str, uid: str, decision: dict, now: datetime) -> client.CoreV1Event:
    return client.CoreV1Event(
        metadata=client.V1ObjectMeta(generate_name=f"{rollout}.veto.", namespace=namespace),
        involved_object=client.V1ObjectReference(api_version="argoproj.io/v1alpha1", kind="Rollout",
                                                 name=rollout, namespace=namespace, uid=uid),
        reason=REASONS.get(decision["verdict"], "VetoHold"),
        message=message(decision),
        type="Normal" if decision["verdict"] == "promote" else "Warning",
        source=client.V1EventSource(component="veto"),
        reporting_component="veto",
        reporting_instance=os.environ.get("HOSTNAME", "veto"),
        first_timestamp=now, last_timestamp=now, count=1,
    )


def post(context: str | None, namespace: str, rollout: str, decision: dict) -> None:
    load_config(context)
    ro = client.CustomObjectsApi().get_namespaced_custom_object("argoproj.io", "v1alpha1", namespace, "rollouts", rollout)
    body = event_body(namespace, rollout, ro["metadata"]["uid"], decision, datetime.now(UTC))
    client.CoreV1Api().create_namespaced_event(namespace, body)
