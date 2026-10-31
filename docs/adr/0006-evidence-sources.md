# 0006 evidence from prometheus, loki and otel

status: accepted

Shop services send traces to an OTel collector and log to stdout.
The collector turns traces into call edge and request metrics (servicegraph, spanmetrics) for Prometheus,
and ships pod logs to Loki.
Canary and stable are split by the rollouts-pod-template-hash pod label, added by the k8sattributes processor.

Why: works with a normal OTel setup, no veto code inside the apps.
Cost: about 1.5 to 2 GB of the 5 GB VM.
If the hash label does not reach the edge metrics, services emit their own outbound call counter instead.
