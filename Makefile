-include .env

PYTHON := .venv/bin/python

.PHONY: check-python test-unit test-graph test-fast test-integration test-all db-up db-migrate db-current db-test

check-python:
	@test -x "$(PYTHON)" || (echo ".venv가 없습니다. ./scripts/bootstrap_python.sh를 실행해 주세요." >&2; exit 1)
	@$(PYTHON) -m scripts.check_python_version

test-unit: check-python
	$(PYTHON) -m pytest tests -m unit -v

test-graph: check-python
	$(PYTHON) -m pytest tests -m graph_flow -v

test-fast: check-python
	$(PYTHON) -m pytest tests -m "not integration" -v

test-integration: check-python
	$(PYTHON) -m pytest -m "integration and not postgres" tests/integration -v

test-all: check-python
	$(PYTHON) -m pytest tests -m "not integration" -v

db-up:
	docker compose up -d postgres

db-migrate: check-python
	$(PYTHON) -m alembic upgrade head

db-current: check-python
	$(PYTHON) -m alembic current

db-test: check-python
	TEST_DATABASE_URL="$(DATABASE_URL)" $(PYTHON) -m pytest -m postgres tests/integration -v
