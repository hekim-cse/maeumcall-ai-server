import os

import pytest


def pytest_collection_modifyitems(items):
    enabled = os.getenv("HF_LOCAL_MODEL_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
    if enabled:
        return
    skip = pytest.mark.skip(reason="set HF_LOCAL_MODEL_ENABLED=1 to run real-model integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
