test-unit:
	python -m pytest -m unit -v

test-graph:
	python -m pytest -m graph_flow -v

test-fast:
	python -m pytest -m "unit or graph_flow" -v

test-integration:
	python -m pytest -m integration tests/integration -v

test-all:
	python -m pytest -v
