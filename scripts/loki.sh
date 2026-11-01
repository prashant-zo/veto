#!/usr/bin/env bash
# usage: scripts/loki.sh 'logql' [since]
set -euo pipefail
kubectl --context kind-veto -n monitoring port-forward svc/loki 13100:3100 > /dev/null 2>&1 &
pf=$!
trap 'kill $pf 2>/dev/null' EXIT
sleep 2
curl -s -G localhost:13100/loki/api/v1/query_range --data-urlencode "query=$1" \
  --data-urlencode "since=${2:-5m}" --data-urlencode "limit=20" | python3 -c '
import sys, json
noise = {"k8s_cluster_uid", "k8s_pod_uid", "k8s_pod_start_time", "container_image_name", "k8s_node_name",
         "log_file_path", "logtag", "observed_timestamp", "scope_name", "scope_version", "log_iostream"}
r = json.load(sys.stdin)["data"]["result"]
if not r:
    print("no logs")
for s in r:
    print({k: v for k, v in s["stream"].items() if k not in noise})
    for v in s["values"][:3]:
        print("   ", v[1])
'
