.PHONY: help state sync scan hooks smoke up down stack

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

stack: ## install argo rollouts and the observability stack
	helm repo add argo https://argoproj.github.io/argo-helm --force-update
	helm upgrade --install argo-rollouts argo/argo-rollouts -n argo-rollouts --create-namespace --version $(ROLLOUTS_CHART) -f demo/stack/argo-rollouts.yaml --wait
