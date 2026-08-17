import pytest

from llm.errors import ScenarioStateValidationError
from services.flow.reservation.common.availability_contract import (
    validate_availability_result,
)
from services.flow.reservation.common.availability_provider import (
    AvailabilityProviderConfigurationError,
    CatalogAvailabilityProvider,
)
from services.flow.reservation.restaurant.availability import (
    resolve_restaurant_availability,
)

pytestmark = pytest.mark.unit


def test_availability_result_requires_exact_contract():
    with pytest.raises(ScenarioStateValidationError):
        validate_availability_result(
            {
                "availability_status": "available",
                "availability_reason": None,
                "available_time": None,
                "alternative_times": [],
            }
        )


def test_client_supplied_result_cannot_override_server_catalog():
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

    assert result["availability_status"] == "unavailable"
    assert result["available_time"] is None
    assert result["alternative_times"] == ["저녁 6시", "저녁 8시"]


def test_unlisted_time_is_not_assumed_available():
    result = resolve_restaurant_availability(
        {"date": "내일", "time": "저녁 7시", "party_size": "2명"}
    )

    assert result["availability_status"] == "unavailable"
    assert result["alternative_times"] == ["저녁 6시", "저녁 8시"]


def test_listed_time_uses_declared_catalog_result():
    result = resolve_restaurant_availability(
        {"date": "내일", "time": "오후 6시", "party_size": "2명"}
    )

    assert result["availability_status"] == "available"
    assert result["available_time"] == "저녁 6시"


def test_catalog_schema_failure_is_an_operational_error(tmp_path):
    catalog_path = tmp_path / "reservation_catalog.json"
    catalog_path.write_text('{"schema_version": 999, "scenarios": {}}', encoding="utf-8")

    with pytest.raises(AvailabilityProviderConfigurationError) as exc_info:
        CatalogAvailabilityProvider(catalog_path)

    assert exc_info.value.code == "AVAILABILITY_PROVIDER_CONFIGURATION_ERROR"
    assert exc_info.value.status_code == 500
