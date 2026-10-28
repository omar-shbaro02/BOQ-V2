.PHONY: bootstrap generate check-generated check-secrets test lint typecheck build up down api web package-installers verify-r10

COMPOSE ?= podman compose

bootstrap:
	python3 -m venv .venv
	.venv/bin/pip install -r services/api/requirements.lock
	.venv/bin/pip install --no-deps -e services/api
	npm install
	$(MAKE) generate

generate:
	python3 scripts/generate_contracts.py

check-generated:
	python3 scripts/generate_contracts.py --check

check-secrets:
	python3 scripts/check_secrets.py

verify-r10:
	.venv/bin/python scripts/verify_r10.py $(R10_ARGS)

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check services/api scripts
	.venv/bin/ruff format --check services/api scripts
	npm run lint:web

typecheck:
	.venv/bin/python -m compileall -q services/api/app scripts
	npm run typecheck:web

build:
	npm run build:web

up:
	$(COMPOSE) up -d postgres

down:
	$(COMPOSE) down

api:
	PYTHONPATH=services/api .venv/bin/uvicorn app.main:app --reload --reload-dir services/api/app

web:
	npm run dev:web

package-installers:
	sh scripts/package_installers.sh
