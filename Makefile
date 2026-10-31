.PHONY: help state sync scan hooks

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
