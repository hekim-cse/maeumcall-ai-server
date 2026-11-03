import json

import pytest

from scripts.probe_gguf_structured_nlu import safe_output_shape

pytestmark = pytest.mark.unit


def test_shape_capture_never_persists_generated_values():
    raw = json.dumps(
        {
            "user_action": "provide_details",
            "change_field": None,
            "fields": {"reason": "private generated value", "date": None},
            "extra": "another private generated value",
        }
    )

    shape = safe_output_shape(
        raw,
        field_names=("reason", "date"),
        actions=frozenset({"provide_details", "unknown"}),
    )

    assert shape == {
        "json_object": True,
        "user_action": "provide_details",
        "present_field_names": ["reason"],
        "change_field": None,
    }
    assert "private generated value" not in json.dumps(shape)


@pytest.mark.parametrize("change_field", [["private generated value"], {"secret": "private generated value"}])
def test_shape_capture_redacts_non_scalar_change_field(change_field):
    raw = json.dumps({"user_action": "provide_details", "change_field": change_field})
    shape = safe_output_shape(
        raw,
        field_names=("reason",),
        actions=frozenset({"provide_details"}),
    )

    assert shape["change_field"] == "__other__"
    assert "private generated value" not in json.dumps(shape)
