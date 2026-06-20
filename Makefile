.DEFAULT_GOAL := help
.PHONY: help install test lint fmt demo serve-mcp serve-http build

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## editable install with dev + mcp extras
	python -m pip install -e ".[dev,mcp]"

test:  ## run the test suite
	pytest -q

lint:  ## ruff check (no changes)
	ruff check src/distillory tests

fmt:  ## ruff autofix
	ruff check --fix src/distillory tests

demo:  ## run the offline quickstart example
	python examples/quickstart.py

serve-mcp:  ## run the MCP server on ./brain.db
	mem serve --mcp --db ./brain.db

serve-http:  ## run the HTTP API on :7878
	mem serve --http --db ./brain.db

build:  ## build the wheel
	python -m pip install -q build && python -m build
