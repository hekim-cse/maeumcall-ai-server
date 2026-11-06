"""Empty model detail actions must retry rather than pass as unknown."""

import pytest

from services.flow.service_workflow.structured import _validate_analysis
from services.flow.support.contracts import SERVICE_REQUEST_SPEC


def _parsed(action: str, *, product_type: str | None = None) -> dict:
    fields = {key: None for key in SERVICE_REQUEST_SPEC.field_keys}
    fields["product_type"] = product_type
    return {
        "intent": SERVICE_REQUEST_SPEC.intent,
        "fields": fields,
        "user_action": action,
        "change_field": None,
    }


@pytest.mark.parametrize("product_type", [None, "   "])
def test_empty_provide_details_remains_invalid(product_type: str | None) -> None:
    with pytest.raises(ValueError, match="requires at least one current-turn field"):
        _validate_analysis(
            SERVICE_REQUEST_SPEC,
            _parsed("provide_details", product_type=product_type),
            conversation_state="greeting",
            current_fields={key: None for key in SERVICE_REQUEST_SPEC.field_keys},
        )


def test_real_detail_remains_provide_details() -> None:
    result = _validate_analysis(
        SERVICE_REQUEST_SPEC,
        _parsed("provide_details", product_type="선풍기"),
        conversation_state="greeting",
        current_fields={key: None for key in SERVICE_REQUEST_SPEC.field_keys},
    )
    assert result["user_action"] == "provide_details"
    assert result["fields"]["product_type"] == "선풍기"


def test_unknown_with_a_field_remains_invalid() -> None:
    with pytest.raises(ValueError, match="must not include current-turn fields"):
        _validate_analysis(
            SERVICE_REQUEST_SPEC,
            _parsed("unknown", product_type="선풍기"),
            conversation_state="greeting",
            current_fields={key: None for key in SERVICE_REQUEST_SPEC.field_keys},
        )
