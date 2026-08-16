test-unit:
	python -m pytest tests -m unit -v

test-graph:
	python -m pytest tests -m graph_flow -v

test-fast:
	python -m pytest tests -m "not integration" -v

test-integration:
	python -m pytest -m integration tests/integration -v

test-all:
	python -m pytest tests -m "not integration" -v
