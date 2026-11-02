.PHONY: help state sync scan hooks smoke up down stack rollouts prometheus loki otel shop release abort promote test pf probe evidence bundle judge judge-all image deploy gate-on gate-off verdict serve eval attacks site-data site-preview rescore

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

abort: ## abort a canary: make abort SVC=checkout
	kubectl argo rollouts --context kind-veto -n shop abort $(SVC)

promote: ## promote a canary: make promote SVC=checkout
	kubectl argo rollouts --context kind-veto -n shop promote $(SVC)

test: ## run unit tests
	uv run pytest -q

pf: ## port-forward prometheus and loki to localhost
	@bash scripts/pf.sh start

probe: ## ask every source about a rollout: make probe SVC=checkout
	uv run --env-file .env veto probe --service $(SVC)

WINDOW ?= 2m

evidence: ## canary evidence from metrics, edges and logs: make evidence SVC=checkout [WINDOW=2m]
	uv run --env-file .env veto evidence --service $(SVC) --window $(WINDOW)

bundle: ## save the bundle the judge sees: make bundle SVC=checkout [CASE=pr-3 saves to eval/cases]
	uv run --env-file .env veto bundle --service $(SVC) --window $(WINDOW) --out $(if $(CASE),eval/cases/$(CASE).json,.local/bundle.json)

CASES ?= control pr-1 pr-2 pr-3 pr-4 pr-5 pr-6 pr-7

judge: ## judge a saved bundle: make judge CASE=pr-3 [ONLY=fallback]
	uv run --env-file .env veto judge --bundle eval/cases/$(CASE).json --out eval/runs/$(CASE).json $(if $(ONLY),--only $(ONLY))

judge-all: ## judge every saved case one after another
	@for c in $(CASES); do $(MAKE) --no-print-directory judge CASE=$$c ONLY=$(ONLY); echo; done

VETO_IMAGE ?= veto:dev
GATED = {"spec":{"strategy":{"canary":{"steps":[{"setWeight":50},{"pause":{"duration":"150s"}},{"analysis":{"templates":[{"templateName":"veto","clusterScope":true}],"args":[{"name":"namespace","value":"shop"},{"name":"rollout","value":"$(SVC)"}]}}]}}}}
MANUAL = {"spec":{"strategy":{"canary":{"steps":[{"setWeight":50},{"pause":{}}]}}}}

image: ## build the veto image and load it into kind
	docker build -t $(VETO_IMAGE) .
	kind load docker-image $(VETO_IMAGE) --name veto

deploy: ## run veto in the cluster, model keys go from .env into secret veto-model
	kubectl --context kind-veto apply -f deploy/veto/namespace.yaml
	@mkdir -p .local && grep -E '^VETO_(MODEL|FALLBACK)_[A-Z_]+=|^VETO_GITHUB_TOKEN=' .env > .local/veto-secret.env
	@if grep -q "=[\"']" .local/veto-secret.env; then rm -f .local/veto-secret.env; echo "remove the quotes around values in .env first"; exit 1; fi
	@kubectl --context kind-veto -n veto create secret generic veto-model --from-env-file=.local/veto-secret.env --dry-run=client -o yaml | kubectl --context kind-veto apply -f -
	@rm -f .local/veto-secret.env
	kubectl --context kind-veto apply -f deploy/veto/ -f deploy/argo/
	kubectl --context kind-veto -n veto rollout restart deploy/veto
	kubectl --context kind-veto -n veto rollout status deploy/veto --timeout 120s

gate-on: ## veto decides canaries of a rollout after 150s: make gate-on SVC=checkout
	kubectl --context kind-veto -n shop patch rollout $(SVC) --type merge -p '$(GATED)'

gate-off: ## back to a manual pause: make gate-off SVC=checkout
	kubectl --context kind-veto -n shop patch rollout $(SVC) --type merge -p '$(MANUAL)'

verdict: ## rollout status and the last veto event: make verdict SVC=checkout
	-@kubectl argo rollouts --context kind-veto -n shop status $(SVC) --timeout 5s
	@kubectl --context kind-veto -n shop get events --sort-by=.lastTimestamp -o custom-columns=REASON:.reason,MESSAGE:.message --no-headers | grep '^Veto' | tail -1

serve: ## run veto on localhost:8088 against the port-forwards
	uv run --env-file .env uvicorn veto.serve.app:app --port 8088

eval: ## score veto and a metrics-only baseline on eval/cases: make eval [ONLY=fallback] [REPEAT=3]
	uv run --env-file .env veto eval --repeat $(or $(REPEAT),1) $(if $(ONLY),--only $(ONLY))

attacks: ## plant 80 prompt injections in saved cases, count what gets through: make attacks [ONLY=fallback]
	uv run --env-file .env veto attacks $(if $(ONLY),--only $(ONLY))

site-data: ## judge every case again and write site/data.json for the replay page
	$(MAKE) --no-print-directory judge-all
	uv run veto site

site-preview: ## serve the replay page on localhost:8090
	@echo "open http://localhost:8090"
	uv run python -m http.server 8090 -d site

rescore: ## score saved results again with the current labels, no model calls
	uv run veto eval --rescore eval/results/muse-spark-open-1026.json
