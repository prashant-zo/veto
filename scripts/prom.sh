#!/usr/bin/env bash
# usage: scripts/prom.sh 'promql'
set -euo pipefail
kubectl --context kind-veto -n monitoring port-forward svc/prometheus-server 19090:80 > /dev/null 2>&1 &
pf=$!
trap 'kill $pf 2>/dev/null' EXIT
sleep 2
curl -s -G localhost:19090/api/v1/query --data-urlencode "query=$1" | python3 -c '
import sys, json
noise = {"app_kubernetes_io_instance", "app_kubernetes_io_name", "component", "controller_revision_hash",
         "pod_template_generation", "node", "pod", "namespace", "otel_scope_name", "collector_instance_id",
         "k8s_cluster_uid", "k8s_pod_uid", "k8s_pod_start_time", "container_image_name", "k8s_node_name"}
d = json.load(sys.stdin)
if d.get("status") != "success":
    print(d); sys.exit(1)
res = d["data"]["result"]
if not res:
    print("no data")
for r in res:
    print(r["value"][1], {k: v for k, v in r["metric"].items() if k not in noise})
'
