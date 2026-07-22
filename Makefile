.DEFAULT_GOAL := help
.PHONY: help install lint type test cov run eval docker

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime + dev dependencies (editable)
	pip install -e ".[dev]"

lint: ## Ruff lint + format check
	ruff check app tests evals
	ruff format --check app tests evals

type: ## Static type check
	mypy app evals

test: ## Run the test suite
	pytest

cov: ## Run tests with the >80% coverage gate
	pytest --cov=app --cov-report=term-missing --cov-fail-under=80

eval: ## Validate the copy scorer against human A/B preferences
	python -m evals --min-accuracy 0.8

# Requires OPENAI_API_KEY in the environment. Costs real money (~$0.02 with
# gpt-4o-mini); the run prints what it actually spent. See docs/EVALUATION.md.
eval-real: ## Score the LLM judge against a real model and write real-model-report.json
	LLM_MODE=real \
	LLM_BASE_URL=https://api.openai.com/v1 \
	LLM_API_KEY=$$OPENAI_API_KEY \
	LLM_MODEL=gpt-4o-mini \
	python -m evals --json real-model-report.json

run: ## Run the API + demo UI locally
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker: ## Build the container image
	docker build -t campaign-studio:local .
