from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from llm.errors import AIServiceError, ScenarioStateValidationError
from services.flow.reservation.common.availability_contract import (
    validate_availability_result,
)

CATALOG_SCHEMA_VERSION = 1
DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "reservation_availability_catalog.json"
)


class AvailabilityProviderConfigurationError(AIServiceError):
    status_code = 500
    code = "AVAILABILITY_PROVIDER_CONFIGURATION_ERROR"
    public_message = "예약 훈련 일정 구성이 올바르지 않습니다."


@dataclass(frozen=True)
class AvailabilityQuery:
    scenario_key: str
    requested_time: str


class AvailabilityProvider(Protocol):
    def resolve(self, query: AvailabilityQuery) -> dict[str, object]: ...


class CatalogAvailabilityProvider:
    """Resolve training availability from a validated, versioned schedule catalog."""

    def __init__(self, catalog_path: Path) -> None:
        self._catalog_path = catalog_path
        self._scenarios = self._load_catalog(catalog_path)

    def resolve(self, query: AvailabilityQuery) -> dict[str, object]:
        requested_time = query.requested_time.strip()
        if not requested_time:
            raise ScenarioStateValidationError("requested_time is required for availability lookup")

        scenario = self._scenarios.get(query.scenario_key)
        if scenario is None:
            raise AvailabilityProviderConfigurationError(
                f"availability scenario is not configured: {query.scenario_key}"
            )

        available_requests = scenario["available_requests"]
        available_slots = list(dict.fromkeys(available_requests.values()))
        if requested_time in available_requests:
            result = {
                "availability_status": "available",
                "availability_reason": None,
                "available_time": available_requests[requested_time],
                "alternative_times": [],
            }
        else:
            result = {
                "availability_status": "unavailable",
                "availability_reason": "requested_time_not_in_schedule",
                "available_time": None,
                "alternative_times": available_slots,
            }

        try:
            return validate_availability_result(result)
        except ScenarioStateValidationError as exc:
            raise AvailabilityProviderConfigurationError(str(exc)) from exc

    @staticmethod
    def _load_catalog(catalog_path: Path) -> dict[str, dict[str, dict[str, str]]]:
        try:
            raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AvailabilityProviderConfigurationError(
                f"availability catalog could not be loaded: {catalog_path}"
            ) from exc

        if not isinstance(raw, dict) or raw.get("schema_version") != CATALOG_SCHEMA_VERSION:
            raise AvailabilityProviderConfigurationError(
                "availability catalog schema_version is unsupported"
            )

        scenarios = raw.get("scenarios")
        if not isinstance(scenarios, dict) or not scenarios:
            raise AvailabilityProviderConfigurationError(
                "availability catalog scenarios must be a non-empty object"
            )

        validated: dict[str, dict[str, dict[str, str]]] = {}
        for scenario_key, value in scenarios.items():
            if not isinstance(scenario_key, str) or not scenario_key.strip():
                raise AvailabilityProviderConfigurationError(
                    "availability catalog scenario key is invalid"
                )
            if not isinstance(value, dict) or set(value) != {"available_requests"}:
                raise AvailabilityProviderConfigurationError(
                    f"availability catalog entry is invalid: {scenario_key}"
                )

            requests = value["available_requests"]
            if (
                not isinstance(requests, dict)
                or not requests
                or any(
                    not isinstance(request, str)
                    or not request.strip()
                    or not isinstance(slot, str)
                    or not slot.strip()
                    for request, slot in requests.items()
                )
            ):
                raise AvailabilityProviderConfigurationError(
                    f"availability requests are invalid: {scenario_key}"
                )

            normalized_requests = {
                request.strip(): slot.strip() for request, slot in requests.items()
            }
            validated[scenario_key] = {"available_requests": normalized_requests}

        return validated


@lru_cache(maxsize=1)
def get_availability_provider() -> AvailabilityProvider:
    configured_path = os.getenv("RESERVATION_AVAILABILITY_CATALOG_PATH")
    catalog_path = Path(configured_path).expanduser() if configured_path else DEFAULT_CATALOG_PATH
    return CatalogAvailabilityProvider(catalog_path)
