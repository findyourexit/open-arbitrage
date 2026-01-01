PYTHON ?= python3

.PHONY: fmt lint typecheck test ci install-dev

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

fmt:
	ruff format .

lint:
	ruff check .
	ruff format --check .

# Keep mypy separate so type stubs load correctly

typecheck:
	mypy open_arbitrage

test:
	pytest

ci: lint typecheck test
