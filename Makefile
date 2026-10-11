.PHONY: dev install test build verify release-check clean

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install --no-deps -e packages/grip-core -e packages/grip-python -e engine

dev:
	.venv/bin/python -m app.main

test:
	PYTHONPATH="packages/grip-core/src:packages/grip-python/src:engine/src:." .venv/bin/pytest -v tests/ packages/grip-python/tests/

release-check:
	.venv/bin/python scripts/release_check.py

build:
	.venv/bin/python scripts/build.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist build *.egg-info