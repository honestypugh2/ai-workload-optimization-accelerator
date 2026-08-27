.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help sync lint format typecheck test benchmark evaluate scenarios all

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

sync: ## Install dependencies with uv
	$(UV) sync --extra dev

lint: ## Run ruff lint checks
	$(UV) run ruff check .

format: ## Format code with ruff
	$(UV) run ruff format .

typecheck: ## Run pyright type checks
	$(UV) run pyright

test: ## Run pytest
	$(UV) run pytest

scenarios: ## List available workload scenarios
	$(UV) run aiwoa scenario list

benchmark: ## Run the baseline post-call-analytics benchmark
	$(UV) run aiwoa benchmark run --scenario post-call-analytics \
		--config workload-scenarios/post-call-analytics/benchmarks/baseline-batch.yaml

evaluate: ## Run the member-id evaluation
	$(UV) run aiwoa evaluate run --scenario post-call-analytics \
		--config workload-scenarios/post-call-analytics/evaluations/member-id.yaml

all: sync lint format typecheck test ## Run the full local quality gate
