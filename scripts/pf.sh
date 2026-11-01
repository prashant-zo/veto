#!/usr/bin/env bash
# start or stop local port-forwards for prometheus and loki
set -uo pipefail
dir="$(git rev-parse --show-toplevel)/.local"
mkdir -p "$dir"
case "${1:-start}" in
  start)
    "$0" stop > /dev/null 2>&1
    kubectl --context kind-veto -n monitoring port-forward svc/prometheus-server 19090:80 > /dev/null 2>&1 &
    echo $! > "$dir/pf-prom.pid"
    kubectl --context kind-veto -n monitoring port-forward svc/loki 13100:3100 > /dev/null 2>&1 &
    echo $! > "$dir/pf-loki.pid"
    sleep 2
    echo "prometheus on localhost:19090, loki on localhost:13100"
    ;;
  stop)
    for f in "$dir"/pf-*.pid; do
      [ -f "$f" ] && kill "$(cat "$f")" 2> /dev/null
      rm -f "$f"
    done
    echo "port-forwards stopped"
    ;;
esac
