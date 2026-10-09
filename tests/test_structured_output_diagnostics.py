import logging

import pytest

from llm.structured_output import (
    StructuredKeyError,
    complete_validated_json,
    require_exact_keys,
)


def test_missing_schema_key_is_logged_without_model_content(caplog):
    outputs = iter(
        [
            '{"intent":"reservation","private text":"sensitive"}',
            '{"intent":"reservation","selected_time":null}',
        ]
    )

    def validate(parsed):
        require_exact_keys(parsed, {"intent", "selected_time"})
        return parsed

    with caplog.at_level(logging.WARNING):
        result = complete_validated_json(
            [{"role": "user", "content": "example"}],
            completion=lambda messages: next(outputs),
            validator=validate,
            operation="test_schema_diagnostics",
        )

    assert result["selected_time"] is None
    assert "missing=['selected_time'] unexpected_count=1" in caplog.text
    assert "sensitive" not in caplog.text
    assert "private text" not in caplog.text


def test_structured_key_error_preserves_exact_key_contract():
    with pytest.raises(StructuredKeyError) as exc_info:
        require_exact_keys({"intent": "reservation"}, {"intent", "selected_time"})

    assert exc_info.value.missing == {"selected_time"}
    assert exc_info.value.unexpected == set()
