PYTHON ?= python3

.PHONY: fmt lint typecheck test cov ci install-dev

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

fmt:
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

# Keep mypy separate so type stubs load correctly
typecheck:
	$(PYTHON) -m mypy open_arbitrage

test:
	$(PYTHON) -m pytest

cov:
	$(PYTHON) -m pytest --cov=open_arbitrage --cov-report=term-missing

ci: lint typecheck test
