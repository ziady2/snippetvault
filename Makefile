.PHONY: install test lint cover clean fixtures docker

PYTHON ?= python

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

cover:
	$(PYTHON) -m pytest --cov=snippetbox --cov-report=term-missing -q

lint:
	$(PYTHON) -m ruff check src tests

fixtures:
	$(PYTHON) scripts/generate_fixtures.py

clean:
	rm -rf build dist *.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

docker:
	docker build -t snippetbox:dev .
	docker run --rm snippetbox:dev
