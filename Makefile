-include .env

test-unit:
	python -m pytest tests -m unit -v

test-graph:
	python -m pytest tests -m graph_flow -v

test-fast:
	python -m pytest tests -m "not integration" -v

test-integration:
	python -m pytest -m "integration and not postgres" tests/integration -v

test-all:
	python -m pytest tests -m "not integration" -v

db-up:
	docker compose up -d postgres

db-migrate:
	alembic upgrade head

db-current:
	alembic current

db-test:
	TEST_DATABASE_URL="$(DATABASE_URL)" python -m pytest -m postgres tests/integration -v
