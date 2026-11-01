# state

## now
part 3: collectors (prometheus, loki, github)

## plan
1. repo, setup, smoke test
2. cluster and demo shop
3. evidence bundle
4. judge and policy
5. service and argo wiring
6. eval and security tests
7. helm chart and site
8. video and submit

## done
- repo with apache license, push protection on
- project layout, python 3.12 with uv
- gitleaks pre-commit hook, tested with a fake token
- state file, adrs, makefile
- smoke test against baseten: 5 of 5 abort, same ids, mean 3.3s
- meta api card fixed, smoke test: 5 of 5 abort, same ids, mean 3.7s
- muse license read, see adr 0005
- asked friends for blind test prs
- kind cluster veto up, k8s 1.35.0
- argo rollouts and prometheus installed
- loki installed, otlp push and query tested
- otel collector installed, traces to prometheus and logs to loki tested
- shop repo and image built, shop deployed with load
- canary split confirmed in edges, span metrics and logs, abort tested
- 5 scenario prs created with images in kind
- 5 scenario prs created with images in kind

## facts
- mac air m1, 8 GB ram, macOS 15.8.1, arm64
- repo path: /Users/prashant/Documents/The Helios Project/DevOps/Project/veto (has spaces, always quote)
- all projects live in .../DevOps/Project/
- python 3.12.13 via uv, system python is 3.14 and unused
- colima 0.10.1, default profile 4 cpu 5 GiB, docker runtime
- kind 0.31.0, kubectl 1.36.0, helm 3.20.2, gitleaks 8.30.1, gh 2.103.3, pre-commit 4.6.0
- kubectl-argo-rollouts plugin v1.10.0 from argoproj/tap, trusted
- git user prashant-zo, noreply email, push over ssh
- env vars: VETO_MODEL_BASE_URL, VETO_MODEL_NAME, VETO_MODEL_API_KEY
- openai python client 3.42.0, chat.completions works on both providers
- main judge: meta-models/muse-spark-open-1026 at https://inference.baseten.co/v1, config in .env
- baseten: reasoning comes in message.reasoning_content, content is clean json
- fallback judge: muse-spark-1.3 at https://api.meta.ai/v1, config in .env.meta
- meta api: chat completions works, reasoning not returned, only counted in usage
- both accept response_format json_object
- latency 3 to 4.5s per call on a small bundle, both providers
- cluster name: veto, context kind-veto
- kind node kindest/node:v1.35.0, containerd 2.2.0, one control-plane node
- argo rollouts chart 2.43.8, app v1.10.1, namespace argo-rollouts
- prometheus chart 29.40.3, server only, namespace monitoring, svc prometheus-server port 80
- loki chart 20.2.1 from grafana-community repo, monolithic, filesystem 2Gi, auth off, svc loki port 3100
- loki otlp push: http://loki.monitoring.svc:3100/otlp, service.name becomes label service_name
- otel collector chart 0.178.1, contrib v0.163.2, daemonset otel-collector-agent, svc otel-collector (otlp grpc 4317, http 4318), metrics on pod port 8889 scraped by prometheus
- otel component names: file_log, k8s_attributes, otlp_http (old names deprecated)
- pod labels become attributes named exactly like the label (run, rollouts-pod-template-hash), prometheus label rollouts_pod_template_hash
- edge metric: traces_service_graph_request_total{client, server, failed, client_rollouts_pod_template_hash, server_rollouts_pod_template_hash}, confirmed, uninstrumented callers show as client "user"
- request metric: traces_span_metrics_calls_total{service_name, span_kind, span_name, status_code, server_address, rollouts_pod_template_hash}, filter by span_kind, asgi also adds SPAN_KIND_INTERNAL spans
- loki log fields: service_name, service_namespace, k8s_pod_name, k8s_namespace_name, pod labels by their own key
- shop app env: OTEL_TRACES_EXPORTER=otlp_proto_http, OTEL_SEMCONV_STABILITY_OPT_IN=http, OTEL_BSP_SCHEDULE_DELAY=1000
- pods need the app.kubernetes.io/name label, else service_name becomes the replicaset name
- servicegraph store ttl 10s, with the 2s default about 20 percent of edges went to "unknown"
- loki query: {service_name="checkout"} | rollouts_pod_template_hash="<hash>"
- shop log format: LEVEL logger message key=value
- prometheus kubernetes-pods job honors labels, so job and instance on span metrics come from the app
- idle vm memory: 0.8 GiB used of 4.9 GiB
- demo shop repo: prashant-zo/veto-demo-shop at .../DevOps/Project/veto-demo-shop, one image veto-shop:<tag>, built with make build [PR=n], loaded into kind
- image tag format: pr-<number>-<shortsha>
- base image: veto-shop:main-a13119d
- shop libs: fastapi 0.162.0, starlette 1.10.0, uvicorn 0.54.0, httpx 0.28.1, otel sdk 1.45.2, instrumentation 0.66b2
- shop: rollouts checkout, pricing, payments in ns shop, 2 replicas, canary setWeight 50 then pause, svc port 8080
- loadgen: ns load, busybox wget about 5 rps to checkout
- query helpers: scripts/prom.sh and scripts/loki.sh
- start a canary: make release SVC=checkout TAG=pr-1-abc1234
- abort: make abort SVC=checkout, then make release with the stable tag to get Healthy
- promote: make promote SVC=checkout
- test image veto-shop:pr-0-a13119d is the same code as main, only for canary tests
- runbook: docs/runbook.md
- scenario prs in veto-demo-shop, all open from main, never merge, see adr 0007:
  #1 cache-prices veto-shop:pr-1-89fe87d expect HOLD
  #2 refactor-helpers veto-shop:pr-2-ac3b97a expect ABORT
  #3 clearer-log veto-shop:pr-3-4a152ce expect PROMOTE
  #4 payments-port veto-shop:pr-4-302d645 expect ABORT by floor
  #5 tidy-logging veto-shop:pr-5-f771cc1 expect ABORT (attack in pr text and a startup log line)
  #6 blind-a veto-shop: held out, answer comes from the author after the eval
  #7 blind-a veto-shop: held out, answer comes from the author after the eval
- scenario prs in veto-demo-shop, all open from main, see adr 0007:
  #1 cache-prices veto-shop:pr-1-89fe87d expect HOLD
  #2 refactor-helpers veto-shop:pr-2-ac3b97a expect ABORT
  #3 clearer-log veto-shop:pr-3-4a152ce expect PROMOTE
  #4 payments-port veto-shop:pr-4-302d645 expect ABORT by floor
  #5 tidy-logging veto-shop:pr--f771cc1 expect ABORT (attack in pr text and a startup log line)

## rules
- commit and push after every step, short lowercase message
- no secrets in git, keys only in .env files or k8s secrets
- read a file before changing it
- in zsh templates write ${var} when a colon follows, $s:a is a zsh modifier
- only muse in demo, eval and site until judging ends
- show "Built with Muse Spark Open" in readme and site
- veto messages say they come from veto, never pose as a person

## open
- blind test prs: link sent to friends, waiting for their prs
- glimmer access not confirmed
- modal and fireworks credits pending
