.PHONY: install dev test verify release-check build sync sync-check clean

# One-time local setup: create the venv and install editable workspace packages.
install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install --no-deps -e packages/core -e packages/engine -e packages/sdk
	.venv/bin/python scripts/sync_vendored.py

# Everything below delegates to the Bun task runner (package.json).
dev:
	bun run dev

test:
	bun run test

verify:
	bun run verify

release-check:
	bun run verify

build:
	bun run build

sync:
	bun run sync

sync-check:
	bun run sync:check

clean:
	bun run clean
