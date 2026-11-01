.PHONY: help state sync scan hooks smoke up down stack rollouts prometheus loki otel shop release

help: ## list targets
	@grep -E '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

state: ## print project snapshot
	@bash scripts/state.sh

sync: ## install python deps
	uv sync

scan: ## scan git history for secrets
	gitleaks git --redact -v

hooks: ## run all pre-commit hooks
	pre-commit run --all-files

smoke: ## call the model and check json output
	uv run --env-file .env python scripts/smoke_baseten.py

up: ## start colima and the kind cluster
	colima status > /dev/null 2>&1 || colima start --cpu 4 --memory 5
	colima ssh -- sudo sysctl -w fs.inotify.max_user_watches=524288 fs.inotify.max_user_instances=512
	kind get clusters | grep -qx veto || kind create cluster --config demo/kind/cluster.yaml
	kubectl config use-context kind-veto

down: ## delete the kind cluster
	kind delete cluster --name veto

ROLLOUTS_CHART := 2.43.8

rollouts: ## install argo rollouts
	helm repo add argo https://argoproj.github.io/argo-helm --force-update
	helm upgrade --install argo-rollouts argo/argo-rollouts -n argo-rollouts --create-namespace --version $(ROLLOUTS_CHART) -f demo/stack/argo-rollouts.yaml --wait

PROM_CHART := 29.40.3

prometheus: ## install prometheus (server only)
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
	helm upgrade --install prometheus prometheus-community/prometheus -n monitoring --create-namespace --version $(PROM_CHART) -f demo/stack/prometheus.yaml --wait

stack: rollouts prometheus loki otel ## install the whole stack

LOKI_CHART := 20.2.1

loki: ## install loki (single binary)
	helm repo add grafana-community https://grafana-community.github.io/helm-charts --force-update
	helm upgrade --install loki grafana-community/loki -n monitoring --create-namespace --version $(LOKI_CHART) -f demo/stack/loki.yaml --wait --timeout 5m

OTEL_CHART := 0.178.1

otel: ## install the otel collector
	helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts --force-update
	helm upgrade --install otel-collector open-telemetry/opentelemetry-collector -n monitoring --create-namespace --version $(OTEL_CHART) -f demo/stack/otel-collector.yaml --wait --timeout 5m

shop: ## deploy the shop and the load generator
	kubectl --context kind-veto apply -f demo/shop/
	kubectl --context kind-veto apply -f demo/load/

release: ## start a canary: make release SVC=checkout TAG=pr-1-abc1234
	kubectl argo rollouts --context kind-veto -n shop set image $(SVC) $(SVC)=veto-shop:$(TAG)
