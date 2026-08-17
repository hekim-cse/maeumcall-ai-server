import os

import pytest


def pytest_collection_modifyitems(items):
    hf_enabled = os.getenv("HF_LOCAL_MODEL_ENABLED", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    postgres_enabled = bool(os.getenv("TEST_DATABASE_URL", "").strip())
    for item in items:
        if "postgres" in item.keywords:
            if not postgres_enabled:
                item.add_marker(
                    pytest.mark.skip(
                        reason="set TEST_DATABASE_URL to run PostgreSQL integration tests"
                    )
                )
        elif "integration" in item.keywords and not hf_enabled:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "set HF_LOCAL_MODEL_ENABLED=1 to run real-model integration tests"
                    )
                )
            )
