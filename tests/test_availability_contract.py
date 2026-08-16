import pytest

from llm.errors import ScenarioStateValidationError
from services.flow.reservation.common.availability_contract import (
    validate_availability_result,
)
from services.flow.reservation.restaurant.availability import (
    resolve_restaurant_availability,
)


pytestmark = pytest.mark.unit


def test_external_availability_result_requires_exact_contract():
    with pytest.raises(ScenarioStateValidationError):
        validate_availability_result(
            {
                "availability_status": "available",
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
            }
        )


def test_external_availability_result_is_used_after_validation():
    result = resolve_restaurant_availability(
        {
            "date": "내일",
            "time": "저녁 7시",
            "party_size": "2명",
            "simulation_result": {
                "availability_status": "available",
                "availability_reason": None,
                "available_time": "저녁 7시",
                "alternative_times": [],
            },
        }
    )

    assert result["availability_status"] == "available"
    assert result["available_time"] == "저녁 7시"


def test_training_conflict_slot_is_declared_by_domain_policy():
    result = resolve_restaurant_availability(
        {"date": "내일", "time": "저녁 7시", "party_size": "2명"}
    )

    assert result["availability_status"] == "unavailable"
    assert result["alternative_times"] == ["저녁 6시", "저녁 8시"]
